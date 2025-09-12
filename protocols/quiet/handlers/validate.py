"""
Handler that validates events using event type validators.
"""
import json
from typing import List, Dict, Any, cast as type_cast
import sqlite3
import importlib
from core.handler import Handler
from core.types import Envelope, validate_envelope_fields
from protocols.quiet.envelope_types import ValidatableEvent, BaseEnvelope
from protocols.quiet.handlers.event_store_handler import purge_event


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
            validate_envelope_fields(envelope, {'event_plaintext', 'event_type'}) and
            envelope.get('sig_checked') is True and
            not envelope.get('validated', False) and
            'event_id' in envelope  # Required for purging if validation fails
        )
    
    def process(self, envelope: Envelope, db: sqlite3.Connection) -> List[Envelope]:
        """Validate event using type-specific validator."""
        
        # We don't need full DecryptedEnvelope validation since event_id comes later
        if not envelope.get('event_plaintext'):
            envelope['error'] = "No event_plaintext to validate"
            return []
            
        event_type = envelope['event_plaintext'].get('type')
        if not event_type:
            envelope['error'] = "No event type specified"
            return []
        
        # Get validator for this type
        validator = self.validators.get(event_type)
        if not validator:
            envelope['error'] = f"No validator for event type: {event_type}"
            return []
        
        # Run validation - validator expects the full envelope
        try:
            is_valid = validator.validate(envelope)
            if is_valid:
                envelope['validated'] = True
                envelope['event_type'] = event_type
            else:
                envelope['error'] = "Validation failed"
                # Purge invalid event from store
                event_id = envelope.get('event_id')
                if event_id:
                    purge_event(event_id, db, "validation_failed")
                return []  # Drop the envelope
        except Exception as e:
            envelope['error'] = f"Validation error: {str(e)}"
            # Purge event on validation error
            event_id = envelope.get('event_id')
            if event_id:
                purge_event(event_id, db, f"validation_error: {str(e)}")
            return []  # Drop the envelope
        
        return [envelope]
    
    def _load_validators(self):
        """Load event type validators."""
        # Load all available event type validators
        event_types = ['identity', 'key', 'transit_secret', 'group', 'channel', 'message', 'invite', 'add', 'network']
        
        for event_type in event_types:
            try:
                module = importlib.import_module(f'protocols.quiet.events.{event_type}.validator')
                self.validators[event_type] = module
            except ImportError as e:
                print(f"Failed to load {event_type} validator: {e}")