"""
Handler that projects validated events to state.
"""
import json
import time
from typing import List
import sqlite3
import importlib
from core.envelope import Envelope
from core.handler import Handler


class ProjectHandler(Handler):
    """
    Projects validated events using their type-specific projectors.
    Consumes: envelopes with validated=True
    Emits: envelopes with projected=True and deltas
    """
    
    def __init__(self):
        # Map of event types to their projector modules
        self.projectors = {}
        self._load_projectors()
    
    @property
    def name(self) -> str:
        return "project"
    
    def filter(self, envelope: Envelope) -> bool:
        """Process validated events that haven't been projected."""
        return (
            envelope.validated is True and
            envelope.projected is not True
        )
    
    def process(self, envelope: Envelope, db: sqlite3.Connection) -> List[Envelope]:
        """Project event to state."""
        
        event_type = envelope.event_type
        projector = self.projectors.get(event_type)
        
        if not projector:
            envelope.error = f"No projector for event type: {event_type}"
            return [envelope]
        
        try:
            # Store the event first
            self._store_event(envelope, db)
            
            # Run projector
            delta = projector.project(envelope.event_plaintext, db)
            
            # Mark as projected
            envelope.projected = True
            
            # If this event unblocks others, emit unblock events
            unblock_envelopes = self._check_unblocks(envelope.event_id, db)
            
            db.commit()
            
            return [envelope] + unblock_envelopes
            
        except Exception as e:
            db.rollback()
            envelope.error = f"Projection failed: {str(e)}"
            return [envelope]
    
    def _store_event(self, envelope: Envelope, db: sqlite3.Connection):
        """Store validated event in events table."""
        db.execute("""
            INSERT OR IGNORE INTO events 
            (event_id, event_type, network_id, created_at, peer_id, event_data, raw_bytes, validated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            envelope.event_id,
            envelope.event_type,
            envelope.network_id,
            envelope.event_plaintext.get('created_at', 0),
            envelope.peer_id,
            json.dumps(envelope.event_plaintext),
            b'',  # TODO: Store actual 512 bytes
            int(time.time() * 1000)
        ))
    
    def _check_unblocks(self, event_id: str, db: sqlite3.Connection) -> List[Envelope]:
        """Check if this event unblocks any waiting events."""
        cursor = db.execute("""
            SELECT DISTINCT blocked_event_id 
            FROM blocked_by 
            WHERE blocking_event_id = ?
        """, (event_id,))
        
        unblock_envelopes = []
        for row in cursor:
            # Create minimal envelope to trigger re-processing
            unblock_env = Envelope()
            unblock_env.event_id = row['blocked_event_id']
            unblock_env.unblocked = True
            unblock_envelopes.append(unblock_env)
        
        return unblock_envelopes
    
    def _load_projectors(self):
        """Load event type projectors."""
        # For now, just load identity manually
        try:
            identity_module = importlib.import_module('protocols.quiet.event_types.identity')
            self.projectors['identity'] = identity_module.IdentityEventType
        except ImportError as e:
            print(f"Failed to load identity projector: {e}")