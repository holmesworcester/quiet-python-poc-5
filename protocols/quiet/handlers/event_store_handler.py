"""
Handler that stores events and generates event IDs.
"""
import json
import time
from typing import List, Dict, Any
import sqlite3
from core.handler import Handler
from core.crypto import hash
from core.types import Envelope

class EventStoreHandler(Handler):
    """
    Stores events and generates event IDs.
    Consumes: envelopes with sig_checked=True
    Emits: envelopes with event_id and stored=True
    """
    
    @property
    def name(self) -> str:
        return "event_store"
    
    def filter(self, envelope: Envelope) -> bool:
        """Process signed events that need to be stored."""
        return (
            envelope.get('sig_checked') is True and
            not envelope.get('event_id') and
            not envelope.get('stored')
        )
    
    def process(self, envelope: Envelope, db: sqlite3.Connection) -> List[Envelope]:
        """Generate event_id and store event."""
        
        # Get event data
        event_data = envelope.get('event_plaintext')
        if not event_data:
            envelope['error'] = "No event_plaintext to store"
            return [envelope]
        
        # Generate event_id from canonical JSON of signed event
        # For encrypted events, this would be hash of ciphertext
        # For unencrypted events, it's hash of signed plaintext
        event_json = json.dumps(event_data, sort_keys=True)
        event_id = hash(event_json.encode()).hex()
        
        # Add event_id to envelope
        envelope['event_id'] = event_id
        
        # Store event in database
        try:
            db.execute("""
                INSERT OR IGNORE INTO events 
                (event_id, event_type, network_id, created_at, peer_id, event_data, raw_bytes, validated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event_id,
                envelope.get('event_type'),
                envelope.get('network_id'),
                event_data.get('created_at', 0),
                envelope.get('peer_id'),
                event_json,
                b'',  # TODO: Store actual raw bytes for encrypted events
                int(time.time() * 1000)
            ))
            
            db.commit()
            envelope['stored'] = True
            
        except Exception as e:
            envelope['error'] = f"Failed to store event: {str(e)}"
            db.rollback()
        
        return [envelope]