"""
Handler that projects validated events to state.
"""
import json
import time
from typing import List, Dict, Any
import sqlite3
import importlib
from core.handler import Handler
from core.types import Envelope, ValidatedEnvelope, validate_envelope_fields, cast_envelope


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
            envelope.get('validated') is True and
            envelope.get('projected') is not True
        )
    
    def process(self, envelope: Envelope, db: sqlite3.Connection) -> List[Envelope]:
        """Project event to state."""
        
        # Get event type
        event_type = envelope.get('event_type')
        if not event_type:
            envelope['error'] = "No event_type for projection"
            return []
        projector = self.projectors.get(event_type)
        
        if not projector:
            envelope['error'] = f"No projector for event type: {event_type}"
            return [envelope]
        
        try:
            # Handle local metadata for self-created identities
            if envelope.get('self_created') and 'local_metadata' in envelope:
                self._store_local_metadata(envelope, db)
            
            # Run projector - it should emit deltas
            deltas = projector.project(envelope)
            print(f"[project] Generated {len(deltas) if deltas else 0} deltas")
            
            # Apply deltas
            from core.deltas import DeltaApplicator
            if deltas:
                for delta in deltas:
                    print(f"[project] Applying delta: {delta}")
                    DeltaApplicator.apply(delta, db)
            
            # Mark as projected and include deltas
            envelope['projected'] = True
            envelope['deltas'] = deltas
            
            # If this event unblocks others, emit unblock events
            try:
                unblock_envelopes = self._check_unblocks(envelope.get('event_id'), db)
            except sqlite3.OperationalError:
                # Table doesn't exist yet
                unblock_envelopes = []
            
            db.commit()
            
            return [envelope] + unblock_envelopes
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            db.rollback()
            envelope['error'] = f"Projection failed: {str(e)}"
            envelope['projected'] = True  # Mark as projected even on error to prevent loops
            return [envelope]
    
    
    def _store_local_metadata(self, envelope: Envelope, db: sqlite3.Connection):
        """Store local metadata for self-created identities."""
        local_metadata = envelope.get('local_metadata', {})
        event_data = envelope.get('event_plaintext', {})
        
        # For identity events, store private key in identities table
        if envelope.get('event_type') == 'identity' and 'private_key' in local_metadata:
            db.execute("""
                INSERT OR REPLACE INTO identities 
                (identity_id, network_id, private_key, public_key, created_at, name)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                event_data['peer_id'],
                event_data['network_id'],
                local_metadata['private_key'],
                local_metadata['public_key'],
                event_data['created_at'],
                event_data.get('name', 'User')
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
            unblock_env = {
                'event_id': row['blocked_event_id'],
                'unblocked': True
            }
            unblock_envelopes.append(unblock_env)
        
        return unblock_envelopes
    
    def _load_projectors(self):
        """Load event type projectors."""
        # Load all available event type projectors
        event_types = ['identity', 'key', 'transit_secret', 'group', 'channel', 'message', 'invite', 'add', 'network']
        
        for event_type in event_types:
            try:
                module = importlib.import_module(f'protocols.quiet.events.{event_type}.projector')
                self.projectors[event_type] = module
            except ImportError as e:
                print(f"Failed to load {event_type} projector: {e}")