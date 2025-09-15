"""
Validator for identity events.
"""
from typing import Dict, Any
from core.core_types import validator
from protocols.quiet.protocol_types import validate_envelope_fields
from protocols.quiet.events import IdentityEventData, validate_event_data


@validator
def validate(envelope: dict[str, Any]) -> bool:
    """
    Validate an identity event.
    
    Returns True if valid, False otherwise.
    """
    # Ensure we have event_plaintext
    if not validate_envelope_fields(envelope, {'event_plaintext'}):
        return False
    
    event = envelope['event_plaintext']
    
    # Use the registry validator
    if not validate_event_data('identity', event):
        return False
    
    # Check peer_id format (should be hex string of public key)
    try:
        bytes.fromhex(event['peer_id'])
        if len(event['peer_id']) != 64:  # Ed25519 public key is 32 bytes = 64 hex chars
            return False
    except ValueError:
        return False
    
    # Check network_id is present (can be empty for self_created identity)
    if 'network_id' not in event or not isinstance(event['network_id'], str):
        return False

    # For non-self-created identities, network_id must be non-empty
    if not envelope.get('self_created') and not event['network_id']:
        return False
    
    # Check created_at is a positive integer (milliseconds)
    if not isinstance(event['created_at'], int) or event['created_at'] <= 0:
        return False
    
    # Check name if present
    if 'name' in event and not isinstance(event['name'], str):
        return False
    
    # If joining via invite, check invite fields
    if 'invite_code' in event:
        if not isinstance(event['invite_code'], str) or not event['invite_code']:
            return False
    
    return True