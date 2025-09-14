"""
Validator for user events.
"""
from typing import Dict, Any
from core.types import Envelope, validator, validate_envelope_fields
from protocols.quiet.events import UserEventData, validate_event_data


@validator
def validate(envelope: Envelope) -> bool:
    """
    Validate a user event.
    
    Returns True if valid, False otherwise.
    """
    # Ensure we have event_plaintext
    if not validate_envelope_fields(envelope, {'event_plaintext'}):
        return False
    
    event = envelope['event_plaintext']
    
    # Use the registry validator
    if not validate_event_data('user', event):
        return False
    
    # User-specific validation
    # Check peer_id matches envelope peer_id if available
    if 'peer_id' in envelope and event['peer_id'] != envelope['peer_id']:
        return False
    
    # Validate port is in valid range
    port = event.get('port')
    if port is not None and (not isinstance(port, int) or port < 1 or port > 65535):
        return False
    
    # Validate address is not empty
    if 'address' in event and (not event['address'] or not isinstance(event['address'], str)):
        return False
    
    # Validate network_id is not empty
    if 'network_id' in event and not event['network_id']:
        return False
    
    return True