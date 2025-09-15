"""
Validator for message events.
"""
from typing import Any
from core.core_types import validator
from protocols.quiet.protocol_types import validate_envelope_fields
from protocols.quiet.events import MessageEventData, validate_event_data


@validator
def validate(envelope: dict[str, Any]) -> bool:
    """
    Validate a message event.
    
    Checks:
    - Has required fields
    - Message ID is valid
    - Author is the signer
    - Content is not empty
    """
    # Ensure we have event_plaintext
    if not validate_envelope_fields(envelope, {'event_plaintext', 'peer_id'}):
        return False
    
    event_data = envelope['event_plaintext']
    
    # Use the registry validator
    if not validate_event_data('message', event_data):
        return False
    
    # Check author matches peer_id (the signer)
    if event_data.get('peer_id') != envelope.get('peer_id'):
        return False
    
    # Check content is not empty
    if not event_data['content'].strip():
        return False
    
    # Check content length (reasonable limit)
    if len(event_data['content']) > 10000:
        return False
    
    return True