"""
Combined Resolve Dependencies and Unblock handler.

From plan.md:
- Resolves dependencies from validated events and local secrets
- Blocks events with missing dependencies  
- Unblocks events when ALL dependencies are satisfied
- Tracks retry count (max 100) to prevent infinite loops
"""

# Removed core.types import
import sqlite3
import json
import time
from typing import List, Dict, Any, Optional, Tuple
from core.handlers import Handler


def filter_func(envelope: dict[str, Any]) -> bool:
    """
    Process envelopes that need dependency resolution or can trigger unblocking.
    """
    # Don't process envelopes that have already been stored
    if envelope.get('stored') is True:
        return False

    # Resolution case 1: explicit deps declared and not yet valid
    if ('deps' in envelope and envelope.get('deps_included_and_valid') is not True):
        return True

    # Resolution case 2: encrypted stages imply key dependency
    if (envelope.get('transit_ciphertext') is not None and envelope.get('transit_key_id')):
        return True
    if (envelope.get('event_ciphertext') is not None and envelope.get('event_key_id')):
        return True

    # Trigger unblocking: newly validated events might unblock others
    if envelope.get('validated') is True:
        return True

    # Block case: events with missing deps need to be blocked (requires event_id)
    if envelope.get('missing_deps') is True and envelope.get('event_id'):
        return True

    return False


def handler(envelope: dict[str, Any], db: sqlite3.Connection) -> List[dict[str, Any]]:
    """
    Combined handler for dependency resolution and unblocking.

    Args:
        envelope: dict[str, Any] needing resolution or triggering unblocking
        db: Database connection

    Returns:
        List of envelopes - resolved events or unblocked events (NOT the triggering validated event)
    """
    results = []

    # Declare minimal deps if missing, based on stage
    if 'deps' not in envelope:
        deps: List[str] = []
        if envelope.get('transit_ciphertext') is not None and envelope.get('transit_key_id'):
            deps.append(f"transit_key:{envelope['transit_key_id']}")
        elif envelope.get('event_ciphertext') is not None and envelope.get('event_key_id'):
            deps.append(f"event_key:{envelope['event_key_id']}")
        elif 'event_plaintext' in envelope:
            pt = envelope['event_plaintext']
            etype = envelope.get('event_type', '')
            if etype == 'message':
                if pt.get('channel_id'):
                    deps.append(f"channel:{pt['channel_id']}")
                if pt.get('peer_id'):
                    deps.append(f"peer:{pt['peer_id']}")
            elif etype == 'channel':
                if pt.get('group_id'):
                    deps.append(f"group:{pt['group_id']}")
            elif etype == 'user':
                if pt.get('invite_pubkey'):
                    deps.append(f"invite:{pt['invite_pubkey']}")
                if envelope.get('peer_id'):
                    deps.append(f"peer:{envelope['peer_id']}")
        if deps:
            envelope['deps'] = deps
            envelope['deps_included_and_valid'] = False

    # Handle dependency resolution
    if 'deps' in envelope and envelope.get('deps_included_and_valid') is not True:
        resolved_envelope = resolve_dependencies(envelope, db)
        if resolved_envelope and not resolved_envelope.get('missing_deps'):
            # Only re-emit if dependencies were actually resolved or there were none
            results.append(resolved_envelope)
        # If missing deps, will be handled by blocking logic below

    # Handle unblocking logic - validated events trigger unblocking but aren't re-emitted
    if envelope.get('validated') is True:
        # This is a newly validated event - check for blocked events
        event_id = envelope.get('event_id')
        if event_id:
            # Track this completed event for placeholder resolution
            track_completed_event(envelope, db)

            # Check for events waiting on this one
            unblocked = unblock_waiting_events(event_id, db)

            # Also check for events waiting on placeholders that can now be resolved
            request_id = envelope.get('request_id')
            if request_id:
                placeholder_unblocked = unblock_placeholder_events(request_id, db)
                results.extend(placeholder_unblocked)

            results.extend(unblocked)
        # Do NOT re-emit the validated event itself

    # Handle blocking logic
    if envelope.get('missing_deps') is True:
        # This event has missing deps - block it
        block_event(envelope, db)
        # Do NOT emit blocked events

    return results


def resolve_dependencies(envelope: dict[str, Any], db: sqlite3.Connection) -> Optional[dict[str, Any]]:
    """Resolve dependencies for an envelope."""
    deps_needed = envelope.get('deps', [])

    if not deps_needed:
        envelope['deps_included_and_valid'] = True
        envelope['resolved_deps'] = {}
        return envelope

    # Special handling for self-created user events
    # They don't need the invite dependency since the user trusts the invite link
    if (envelope.get('self_created') and
        envelope.get('event_type') == 'user' and
        'event_plaintext' in envelope):
        # Filter out invite dependencies for self-created user events
        deps_needed = [dep for dep in deps_needed if not dep.startswith('invite:')]

    # Try to resolve each dependency
    resolved_deps = {}
    missing_deps = []

    # Check for placeholders in dependencies or peer_id
    has_placeholders = (any(dep.startswith('@generated:') for dep in deps_needed) or
                       envelope.get('peer_id', '').startswith('@generated:'))

    if has_placeholders:
        # Try to resolve placeholders from completed events in the same request
        request_id = envelope.get('request_id')
        if request_id:
            deps_needed = resolve_placeholders_in_list(deps_needed, request_id, db)
            envelope['deps'] = deps_needed  # Update the deps list with resolved placeholders

            # Also resolve placeholders in event_plaintext if needed
            if 'event_plaintext' in envelope:
                envelope['event_plaintext'] = resolve_placeholders_in_dict(
                    envelope['event_plaintext'], request_id, db
                )

            # Also resolve placeholder in peer_id if it's a placeholder
            peer_id = envelope.get('peer_id', '')
            if peer_id.startswith('@generated:'):
                resolved_peer_id = resolve_single_placeholder(peer_id, request_id, db)
                if resolved_peer_id:
                    envelope['peer_id'] = resolved_peer_id
                    # Also update in event_plaintext
                    if 'event_plaintext' in envelope:
                        envelope['event_plaintext']['peer_id'] = resolved_peer_id
                else:
                    # Can't resolve yet, mark as having missing dependencies
                    print(f"[resolve_deps] Could not resolve {peer_id} for request {request_id}")
                    missing_deps.append(peer_id)

    # Continue resolving other dependencies
    for dep_ref in deps_needed:
        # Skip unresolved placeholders
        if dep_ref.startswith('@generated:'):
            missing_deps.append(dep_ref)
            continue

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


def block_event(envelope: dict[str, Any], db: sqlite3.Connection) -> None:
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


def unblock_waiting_events(validated_event_id: str, db: sqlite3.Connection) -> List[dict[str, Any]]:
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
    
    all_deps = [row[0] for row in cursor]  # dep_id is first column
    
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


def track_completed_event(envelope: dict[str, Any], db: sqlite3.Connection) -> None:
    """Track a completed event for placeholder resolution."""
    event_id = envelope.get('event_id')
    event_type = envelope.get('event_type')
    request_id = envelope.get('request_id')

    if not event_id or not event_type or not request_id:
        return

    # Store in a tracking table for placeholder resolution
    try:
        db.execute("""
            INSERT OR REPLACE INTO completed_events
            (event_id, event_type, request_id, created_at)
            VALUES (?, ?, ?, ?)
        """, (event_id, event_type, request_id, int(time.time() * 1000)))
    except:
        pass  # Table might not exist yet


def unblock_placeholder_events(request_id: str, db: sqlite3.Connection) -> List[dict[str, Any]]:
    """Check for blocked events with placeholders that can now be resolved."""
    unblocked = []

    # Find blocked events with placeholder dependencies
    cursor = db.execute("""
        SELECT event_id, envelope_json
        FROM blocked_events
        WHERE missing_deps LIKE '%@generated:%'
    """)

    for row in cursor:
        event_id, envelope_json = row
        try:
            envelope = json.loads(envelope_json)

            # Only process events from the same request
            if envelope.get('request_id') != request_id:
                continue

            # Try to resolve placeholders
            original_deps = envelope.get('deps', [])
            resolved_deps = resolve_placeholders_in_list(original_deps, request_id, db)

            # Check if any placeholders were resolved
            if resolved_deps != original_deps:
                envelope['deps'] = resolved_deps

                # Also resolve placeholders in event data
                if 'event_plaintext' in envelope:
                    envelope['event_plaintext'] = resolve_placeholders_in_dict(
                        envelope['event_plaintext'], request_id, db
                    )

                # Resolve peer_id placeholder if needed
                peer_id = envelope.get('peer_id', '')
                if peer_id.startswith('@generated:'):
                    resolved_peer_id = resolve_single_placeholder(peer_id, request_id, db)
                    if resolved_peer_id:
                        envelope['peer_id'] = resolved_peer_id

                # Check if all placeholders are now resolved
                if not any(dep.startswith('@generated:') for dep in envelope.get('deps', [])):
                    # Remove from blocked events
                    db.execute("DELETE FROM blocked_events WHERE event_id = ?", (event_id,))
                    db.execute("DELETE FROM blocked_event_deps WHERE event_id = ?", (event_id,))

                    # Mark for re-processing
                    envelope['unblocked'] = True
                    envelope['retry_count'] = envelope.get('retry_count', 0) + 1
                    envelope.pop('missing_deps', None)
                    envelope.pop('missing_deps_list', None)
                    envelope['deps_included_and_valid'] = False

                    unblocked.append(envelope)
                else:
                    # Update blocked event with partially resolved placeholders
                    db.execute("""
                        UPDATE blocked_events
                        SET envelope_json = ?
                        WHERE event_id = ?
                    """, (json.dumps(envelope), event_id))

        except Exception as e:
            continue

    return unblocked


def resolve_single_placeholder(placeholder: str, request_id: str, db: sqlite3.Connection) -> Optional[str]:
    """Resolve a single placeholder to an actual event ID."""
    if not placeholder.startswith('@generated:'):
        return placeholder

    # Parse placeholder format: @generated:type:index
    parts = placeholder.split(':')
    if len(parts) != 3:
        return None

    event_type = parts[1]
    index = int(parts[2])

    # Look for validated events of this type in the same request
    # These are tracked when events validate during pipeline processing
    cursor = db.execute("""
        SELECT event_id FROM completed_events
        WHERE event_type = ?
        AND request_id = ?
        ORDER BY created_at
        LIMIT 1 OFFSET ?
    """, (event_type, request_id, index))

    row = cursor.fetchone()
    return row[0] if row else None


def resolve_placeholders_in_list(items: List[str], request_id: str, db: sqlite3.Connection) -> List[str]:
    """Resolve placeholders in a list of strings."""
    resolved = []
    for item in items:
        if item.startswith('@generated:'):
            resolved_id = resolve_single_placeholder(item, request_id, db)
            resolved.append(resolved_id if resolved_id else item)
        else:
            resolved.append(item)
    return resolved


def resolve_placeholders_in_dict(data: Dict[str, Any], request_id: str, db: sqlite3.Connection) -> Dict[str, Any]:
    """Recursively resolve placeholders in a dictionary."""
    result: Dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, str) and value.startswith('@generated:'):
            resolved = resolve_single_placeholder(value, request_id, db)
            result[key] = resolved if resolved else value
        elif isinstance(value, dict):
            result[key] = resolve_placeholders_in_dict(value, request_id, db)
        elif isinstance(value, list):
            result[key] = [
                resolve_single_placeholder(v, request_id, db) if isinstance(v, str) and v.startswith('@generated:') else v
                for v in value
            ]
        else:
            result[key] = value
    return result


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
        # Identity is now a core feature, not stored as events
        # This shouldn't be called anymore since we removed identity dependencies
        return None

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
                'transit_secret': row[0],  # transit_secret
                'network_id': row[1]  # network_id
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
        if row and row[1]:  # unsealed_secret
            return {
                'event_type': 'key',
                'event_id': dep_id,
                'key_id': row[0],  # key_id
                'unsealed_secret': row[1],  # unsealed_secret
                'group_id': row[2],  # group_id
                'validated': True
            }
        return None

    elif dep_type == 'peer':
        # For peer events, always check peers table first to get full data
        # First try to find by peer_id (most common case)
        cursor = db.execute("""
            SELECT peer_id, public_key, identity_id, created_at
            FROM peers
            WHERE peer_id = ?
        """, (dep_id,))

        row = cursor.fetchone()

        # If not found by peer_id and it looks like it could be an identity_id,
        # try looking up by identity_id (for legacy compatibility)
        if not row and len(dep_id) == 32:  # Could be an identity_id
            cursor = db.execute("""
                SELECT peer_id, public_key, identity_id, created_at
                FROM peers
                WHERE identity_id = ?
                LIMIT 1
            """, (dep_id,))
            row = cursor.fetchone()

        if row:
            # row columns: peer_id, public_key, identity_id, created_at
            event_plaintext = {
                'type': 'peer',
                'public_key': row[1],  # public_key
                'identity_id': row[2],  # identity_id
                'created_at': row[3]  # created_at
            }
            # Also update the event's peer_id to the actual peer_id if we resolved by identity
            actual_peer_id = row[0]
            return {
                'event_plaintext': event_plaintext,
                'event_type': 'peer',
                'event_id': actual_peer_id,  # Use actual peer_id
                'validated': True
            }
        return None

    else:
        # For other event types, check if event exists in events table
        cursor = db.execute("""
            SELECT event_type
            FROM events
            WHERE event_id = ? AND purged = 0
        """, (dep_id,))

        row = cursor.fetchone()
        if row:
            # Return minimal envelope - the dependency exists
            return {
                'event_plaintext': {},  # We don't store plaintext anymore
                'event_type': row[0],  # row is a tuple, event_type is first column
                'event_id': dep_id,
                'validated': True
            }

        return None

class ResolveDepsHandler(Handler):
    """Handler for resolve deps."""

    @property
    def name(self) -> str:
        return "resolve_deps"

    def filter(self, envelope: dict[str, Any]) -> bool:
        """Check if this handler should process the envelope."""
        if not isinstance(envelope, dict):
            print(f"[resolve_deps] WARNING: filter got {type(envelope)} instead of dict: {envelope}")
            return False
        return filter_func(envelope)

    def process(self, envelope: dict[str, Any], db: sqlite3.Connection) -> List[dict[str, Any]]:
        """Process the envelope."""
        # resolve_deps handler function returns a list
        return handler(envelope, db)
