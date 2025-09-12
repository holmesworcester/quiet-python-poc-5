"""
Combined Resolve Dependencies and Unblock handler.

From plan.md:
- Resolves dependencies from validated events and local secrets
- Blocks events with missing dependencies  
- Unblocks events when ALL dependencies are satisfied
- Tracks retry count (max 100) to prevent infinite loops
"""

from core.types import Envelope
import sqlite3
import json
import time
from typing import List, Dict, Any, Optional, Tuple


def filter_func(envelope: Envelope) -> bool:
    """
    Process envelopes that need dependency resolution or unblocking.
    """
    # Resolution case: has deps that need resolving
    if ('deps' in envelope and 
        (envelope.get('deps_included_and_valid') is not True or 
         envelope.get('unblocked') is True)):
        return True
    
    # Unblocking case: newly validated or has missing deps
    if (envelope.get('validated') is True or 
        envelope.get('missing_deps') is True):
        return True
    
    return False


def handler(envelope: Envelope, db: sqlite3.Connection) -> List[Envelope]:
    """
    Combined handler for dependency resolution and unblocking.
    
    Args:
        envelope: Envelope needing resolution or triggering unblocking
        db: Database connection
        
    Returns:
        List of envelopes - may include unblocked events
    """
    results = []
    
    # Handle dependency resolution
    if 'deps' in envelope and envelope.get('deps_included_and_valid') is not True:
        resolved_envelope = resolve_dependencies(envelope, db)
        if resolved_envelope:
            results.append(resolved_envelope)
        # If missing deps, will be handled by unblocking logic below
    else:
        results.append(envelope)
    
    # Handle unblocking logic
    if envelope.get('validated') is True:
        # This is a newly validated event - check for blocked events
        unblocked = unblock_waiting_events(envelope.get('event_id'), db)
        results.extend(unblocked)
    elif envelope.get('missing_deps') is True:
        # This event has missing deps - block it
        block_event(envelope, db)
    
    return results


def resolve_dependencies(envelope: Envelope, db: sqlite3.Connection) -> Optional[Envelope]:
    """Resolve dependencies for an envelope."""
    deps_needed = envelope.get('deps', [])
    
    if not deps_needed:
        envelope['deps_included_and_valid'] = True
        envelope['resolved_deps'] = {}
        return envelope
    
    # Try to resolve each dependency
    resolved_deps = {}
    missing_deps = []
    
    for dep_ref in deps_needed:
        dep_type, dep_id = parse_dep_ref(dep_ref)
        dep_data = fetch_dependency(dep_id, dep_type, db)
        
        if dep_data:
            resolved_deps[dep_ref] = dep_data
        else:
            missing_deps.append(dep_ref)
    
    if missing_deps:
        # Still have missing dependencies
        envelope['missing_deps'] = True
        envelope['missing_deps_list'] = missing_deps
        envelope['deps_included_and_valid'] = False
        
        # Will be blocked by the unblocking logic
        return envelope
    else:
        # All dependencies resolved
        envelope['resolved_deps'] = resolved_deps
        envelope['deps_included_and_valid'] = True
        envelope.pop('missing_deps', None)
        envelope.pop('missing_deps_list', None)
        return envelope


def block_event(envelope: Envelope, db: sqlite3.Connection) -> None:
    """Block an event with missing dependencies."""
    event_id = envelope.get('event_id')
    missing_deps_list = envelope.get('missing_deps_list', [])
    retry_count = envelope.get('retry_count', 0)
    
    if not event_id or not missing_deps_list or retry_count >= 100:
        return
    
    try:
        # Store blocked envelope
        db.execute("""
            INSERT OR REPLACE INTO blocked_events 
            (event_id, envelope_json, created_at, missing_deps, retry_count)
            VALUES (?, ?, ?, ?, ?)
        """, (
            event_id,
            json.dumps(envelope),
            int(time.time() * 1000),
            json.dumps(missing_deps_list),
            retry_count
        ))
        
        # Clear and insert dependency tracking
        db.execute("DELETE FROM blocked_event_deps WHERE event_id = ?", (event_id,))
        
        for dep in missing_deps_list:
            dep_event_id = dep.split(':')[-1] if ':' in dep else dep
            db.execute("""
                INSERT INTO blocked_event_deps (event_id, dep_id)
                VALUES (?, ?)
            """, (event_id, dep_event_id))
        
        db.commit()
        
    except Exception as e:
        db.rollback()
        print(f"Failed to block event {event_id}: {e}")


def unblock_waiting_events(validated_event_id: str, db: sqlite3.Connection) -> List[Envelope]:
    """Check and unblock events waiting on this validated event."""
    if not validated_event_id:
        return []
    
    unblocked = []
    
    # Find events blocked on this dependency
    cursor = db.execute("""
        SELECT be.event_id, be.envelope_json, be.retry_count
        FROM blocked_events be
        JOIN blocked_event_deps bed ON be.event_id = bed.event_id
        WHERE bed.dep_id = ?
    """, (validated_event_id,))
    
    blocked_events = cursor.fetchall()
    
    for blocked in blocked_events:
        blocked_event_id = blocked['event_id']
        retry_count = blocked['retry_count']
        
        # Check retry limit
        if retry_count >= 100:
            db.execute("DELETE FROM blocked_events WHERE event_id = ?", (blocked_event_id,))
            continue
        
        # Check if ALL dependencies are now satisfied
        if are_all_deps_satisfied(blocked_event_id, db):
            # Unblock this event
            blocked_envelope = json.loads(blocked['envelope_json'])
            blocked_envelope['unblocked'] = True
            blocked_envelope['retry_count'] = retry_count + 1
            
            # Remove from blocked events
            db.execute("DELETE FROM blocked_events WHERE event_id = ?", (blocked_event_id,))
            
            unblocked.append(blocked_envelope)
    
    db.commit()
    return unblocked


def are_all_deps_satisfied(event_id: str, db: sqlite3.Connection) -> bool:
    """Check if all dependencies for an event are satisfied."""
    cursor = db.execute("""
        SELECT dep_id FROM blocked_event_deps WHERE event_id = ?
    """, (event_id,))
    
    all_deps = [row['dep_id'] for row in cursor]
    
    for dep_id in all_deps:
        # Check if this dependency exists and is not purged
        exists = db.execute("""
            SELECT 1 FROM events 
            WHERE event_id = ? AND purged = 0
            LIMIT 1
        """, (dep_id,)).fetchone()
        
        if not exists:
            return False
    
    return True


def parse_dep_ref(dep_ref: str) -> Tuple[str, str]:
    """Parse dependency reference like 'identity:abc123' into (type, id)."""
    if ':' in dep_ref:
        dep_type, dep_id = dep_ref.split(':', 1)
        return dep_type, dep_id
    else:
        return 'event', dep_ref


def fetch_dependency(dep_id: str, dep_type: str, db: sqlite3.Connection) -> Optional[Dict[str, Any]]:
    """Fetch a dependency - either a validated event or local secret."""
    
    if dep_type == 'identity':
        # Fetch validated identity event
        cursor = db.execute("""
            SELECT event_data, event_type 
            FROM events 
            WHERE event_id = ? AND validated = 1 AND purged = 0
        """, (dep_id,))
        
        row = cursor.fetchone()
        if not row:
            return None
        
        envelope = {
            'event_plaintext': json.loads(row['event_data']) if row['event_data'] else {},
            'event_type': row['event_type'],
            'event_id': dep_id,
            'validated': True
        }
        
        # Also fetch private key from local storage
        cursor = db.execute("""
            SELECT private_key FROM signing_keys 
            WHERE peer_id = ?
        """, (dep_id,))
        
        key_row = cursor.fetchone()
        if key_row and key_row['private_key']:
            envelope['local_metadata'] = {
                'private_key': key_row['private_key']
            }
        
        return envelope
        
    elif dep_type == 'transit_key':
        # Transit keys are local secrets
        cursor = db.execute("""
            SELECT transit_secret, network_id 
            FROM transit_keys 
            WHERE transit_key_id = ?
        """, (dep_id,))
        
        row = cursor.fetchone()
        if row:
            return {
                'transit_secret': row['transit_secret'],
                'network_id': row['network_id']
            }
        return None
        
    elif dep_type == 'key':
        # Key event with unsealed secret
        cursor = db.execute("""
            SELECT key_id, unsealed_secret, group_id
            FROM events 
            WHERE event_id = ? AND event_type = 'key' AND purged = 0
        """, (dep_id,))
        
        row = cursor.fetchone()
        if row and row['unsealed_secret']:
            return {
                'event_type': 'key',
                'event_id': dep_id,
                'key_id': row['key_id'],
                'unsealed_secret': row['unsealed_secret'],
                'group_id': row['group_id'],
                'validated': True
            }
        return None
        
    else:
        # Regular validated events
        cursor = db.execute("""
            SELECT event_data, event_type 
            FROM events 
            WHERE event_id = ? AND validated = 1 AND purged = 0
        """, (dep_id,))
        
        row = cursor.fetchone()
        if row:
            return {
                'event_plaintext': json.loads(row['event_data']) if row['event_data'] else {},
                'event_type': row['event_type'],
                'event_id': dep_id,
                'validated': True
            }
        return None