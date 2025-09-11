"""
Handler that validates events using event type validators.
"""
import json
from typing import List, Dict, Any
import sqlite3
import importlib
from core.envelope import Envelope
from core.handler import Handler


class ValidateHandler(Handler):
    """
    Validates events using their type-specific validators.
    Consumes: envelopes with event_plaintext, sig_checked=True
    Emits: envelopes with validated=True
    """
    
    def __init__(self):
        # Map of event types to their validator modules
        self.validators = {}
        self._load_validators()
    
    @property
    def name(self) -> str:
        return "validate"
    
    def filter(self, envelope: Envelope) -> bool:
        """Process envelopes ready for validation."""
        return (
            envelope.event_plaintext is not None and
            envelope.sig_checked is True and
            not envelope.validated
        )
    
    def process(self, envelope: Envelope, db: sqlite3.Connection) -> List[Envelope]:
        """Validate event using type-specific validator."""
        
        event_type = envelope.event_plaintext.get('type')
        if not event_type:
            envelope.error = "No event type specified"
            return []
        
        # Get validator for this type
        validator = self.validators.get(event_type)
        if not validator:
            envelope.error = f"No validator for event type: {event_type}"
            return []
        
        # Build metadata for validator
        metadata = {
            'network_id': envelope.network_id,
            'peer_id': envelope.peer_id,
            'deps': envelope.included_deps
        }
        
        # Run validation
        try:
            is_valid = validator.validate(envelope.event_plaintext, metadata)
            if is_valid:
                envelope.validated = True
                envelope.event_type = event_type
            else:
                envelope.error = "Validation failed"
        except Exception as e:
            envelope.error = f"Validation error: {str(e)}"
        
        return [envelope]
    
    def _load_validators(self):
        """Load event type validators."""
        # For now, just load identity manually
        # TODO: Dynamic discovery
        try:
            identity_module = importlib.import_module('protocols.quiet.event_types.identity')
            self.validators['identity'] = identity_module.IdentityEventType
        except ImportError as e:
            print(f"Failed to load identity validator: {e}")