"""
Validator for transit secret events.
"""
from typing import Dict, Any
from core.core_types import validator
from protocols.quiet.protocol_types import validate_envelope_fields
from protocols.quiet.events import TransitSecretEventData, validate_event_data


@validator
def validate(envelope: dict[str, Any]) -> bool:
    """
    Validate a transit secret event.
    
    Returns True if valid, False otherwise.
    """
    # Ensure we have event_plaintext
    if not validate_envelope_fields(envelope, {'event_plaintext'}):
        return False
    
    event = envelope['event_plaintext']
    
    # Use the registry validator
    if not validate_event_data('transit_secret', event):
        return False
    
    # Transit secret specific validation
    # Additional validation for transit_key_id length if present
    if 'transit_key_id' in event and (not event['transit_key_id'] or len(event['transit_key_id']) != 64):  # 32 bytes hex
        return False
        
    return True