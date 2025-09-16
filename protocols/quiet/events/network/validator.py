"""
Validator for network events.
"""
from typing import Dict, Any
from core.core_types import validator
from protocols.quiet.protocol_types import validate_envelope_fields
from protocols.quiet.events import NetworkEventData, validate_event_data


@validator
def validate(envelope: dict[str, Any]) -> bool:
    """
    Validate a network event.
    
    Returns True if valid, False if invalid.
    """
    # Ensure we have event_plaintext
    if not validate_envelope_fields(envelope, {'event_plaintext'}):
        return False
    
    event = envelope['event_plaintext']
    
    # Use the registry validator
    if not validate_event_data('network', event):
        return False
    
    # Check that name is not empty
    if not event.get('name', '').strip():
        return False
    
    # Check creator matches identity_id (the signer) for self-created
    # or peer_id for received events
    signer_id = envelope.get('identity_id') or envelope.get('peer_id')
    if event.get('creator_id') != signer_id:
        return False
    
    # For now, don't check duplicates - that would require db access
    # Network events are valid if they have all required fields
    return True