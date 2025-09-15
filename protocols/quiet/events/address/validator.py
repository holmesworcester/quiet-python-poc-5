"""
Validator for address events.
"""
from typing import Dict, Any
from core.core_types import validator


@validator
def validate(envelope: Dict[str, Any]) -> bool:
    """
    Validate an address event.

    Returns True if valid, False if invalid.
    """
    event_data = envelope.get('event_plaintext', {})

    # Check type
    if event_data.get('type') != 'address':
        return False

    # Check required fields
    required_fields = ['type', 'address_id', 'peer_id', 'user_id', 'address', 'port', 'network_id', 'timestamp', 'signature']
    for field in required_fields:
        if field not in event_data:
            return False

    # address_id can be empty (filled by handler)

    # Check that peer_id is not empty
    if not event_data['peer_id']:
        return False

    # Check that user_id is not empty
    if not event_data['user_id']:
        return False

    # Check that network_id is not empty
    if not event_data['network_id']:
        return False

    # Validate port is in valid range
    port = event_data.get('port')
    if not isinstance(port, int) or port < 0 or port > 65535:
        return False

    # Validate address is not empty
    if not event_data['address'] or not isinstance(event_data['address'], str):
        return False

    # Check peer_id matches envelope peer_id (the signer)
    if event_data['peer_id'] != envelope.get('peer_id'):
        return False

    return True