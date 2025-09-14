"""
Validator for key events.
"""
from typing import Dict, Any
from core.types import Envelope, validator, validate_envelope_fields
from protocols.quiet.events import KeyEventData, validate_event_data


@validator
def validate(envelope: Envelope) -> bool:
    """
    Validate a key event.
    
    Returns True if valid, False otherwise.
    """
    # Ensure we have event_plaintext
    if not validate_envelope_fields(envelope, {'event_plaintext'}):
        return False
    
    event = envelope['event_plaintext']
    
    # Use the registry validator
    if not validate_event_data('key', event):
        return False
    
    # Key-specific validation
    # Additional validation for key_id length
    if 'key_id' in event and len(event.get('key_id', '')) != 64:  # 32 bytes hex
        return False
        
    if 'sealed_key' in event and not event['sealed_key']:
        return False
        
    return True