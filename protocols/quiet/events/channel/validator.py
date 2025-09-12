"""
Validator for channel events.
"""
from typing import Dict, Any
from core.types import Envelope, validator, validate_envelope_fields
from protocols.quiet.events import ChannelEventData, validate_event_data


@validator
def validate(envelope: Envelope) -> bool:
    """
    Validate a channel event.
    
    Returns True if valid, False otherwise.
    """
    # Ensure we have event_plaintext
    if not validate_envelope_fields(envelope, {'event_plaintext'}):
        return False
    
    event = envelope['event_plaintext']
    
    # Use the registry validator
    if not validate_event_data('channel', event):
        return False
    
    # Channel-specific validation
    # Check creator matches peer_id (the signer) if available
    if 'peer_id' in envelope and event['creator_id'] != envelope['peer_id']:
        return False
    
    # TODO: In a full implementation, we'd check if the group exists
    # and if the creator is a member of the group
    
    return True