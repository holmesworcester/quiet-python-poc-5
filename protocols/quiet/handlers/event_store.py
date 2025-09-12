"""
Event Store handler - Stores events and manages purging of invalid events.

From plan.md:
- Filter: `write_to_store: true`
- Action: Stores event data in database, including network metadata
- Purge Function: Marks invalid events as purged while keeping event_id for duplicate detection
"""

from core.types import Envelope
import sqlite3
import time
from typing import Optional


def filter_func(envelope: Envelope) -> bool:
    """
    Process envelopes that need to be stored.
    """
    return envelope.get('write_to_store') is True


def handler(envelope: Envelope, db: sqlite3.Connection) -> Envelope:
    """
    Store event data in database.
    
    Args:
        envelope: Envelope with write_to_store flag
        db: Database connection
        
    Returns:
        Envelope with stored: true
    """
    event_id = envelope.get('event_id')
    if not event_id:
        envelope['error'] = "No event_id to store"
        return envelope
    
    # Check if already stored
    cursor = db.execute(
        "SELECT purged FROM events WHERE event_id = ?",
        (event_id,)
    )
    existing = cursor.fetchone()
    
    if existing:
        if existing['purged']:
            envelope['error'] = "Event is purged"
            return envelope
        envelope['stored'] = True
        return envelope
    
    # Store event
    try:
        db.execute("""
            INSERT INTO events (
                event_id,
                event_type,
                event_ciphertext,
                event_key_id,
                key_id,
                unsealed_secret,
                group_id,
                received_at,
                origin_ip,
                origin_port,
                stored_at,
                purged
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event_id,
            envelope.get('event_type'),
            envelope.get('event_ciphertext'),
            envelope.get('event_key_id'),
            envelope.get('key_id'),
            envelope.get('unsealed_secret'),
            envelope.get('group_id'),
            envelope.get('received_at'),
            envelope.get('origin_ip'),
            envelope.get('origin_port'),
            int(time.time() * 1000),
            False  # Not purged
        ))
        
        db.commit()
        envelope['stored'] = True
        
    except Exception as e:
        db.rollback()
        envelope['error'] = f"Failed to store event: {str(e)}"
    
    return envelope


def purge_event(event_id: str, db: sqlite3.Connection, reason: str = "validation_failed") -> bool:
    """
    Purge an event - mark it as invalid but keep event_id for duplicate detection.
    Called by validate handler when validation fails.
    
    Args:
        event_id: The event to purge
        db: Database connection
        reason: Why the event was purged
        
    Returns:
        True if purged successfully
    """
    try:
        # Update event as purged
        db.execute("""
            UPDATE events 
            SET purged = ?, 
                purged_at = ?, 
                purged_reason = ?,
                ttl_expire_at = ?
            WHERE event_id = ?
        """, (
            True,
            int(time.time() * 1000),
            reason,
            int(time.time() * 1000) + (7 * 24 * 60 * 60 * 1000),  # 7 day TTL
            event_id
        ))
        
        # Also delete from any projections if they exist
        db.execute("DELETE FROM projected_events WHERE event_id = ?", (event_id,))
        
        db.commit()
        return True
        
    except Exception as e:
        db.rollback()
        print(f"Failed to purge event {event_id}: {e}")
        return False