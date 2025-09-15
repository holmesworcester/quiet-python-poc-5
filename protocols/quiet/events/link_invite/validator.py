"""
Validator for link_invite events.
"""
from typing import Dict, Any
from core.core_types import validator


@validator
def validate(envelope: Dict[str, Any]) -> bool:
    """
    Validate a link_invite event.

    Returns True if valid, False if invalid.
    """
    event_data = envelope.get('event_plaintext', {})

    # Check type
    if event_data.get('type') != 'link_invite':
        return False

    # Check required fields
    required_fields = ['type', 'peer_id', 'user_id', 'network_id', 'created_at', 'signature']
    for field in required_fields:
        if field not in event_data:
            return False

    # Check that peer_id is not empty
    if not event_data['peer_id']:
        return False

    # Check that user_id is not empty
    if not event_data['user_id']:
        return False

    # Check that network_id is not empty
    if not event_data['network_id']:
        return False

    # Check peer_id matches envelope peer_id (the signer)
    if event_data['peer_id'] != envelope.get('peer_id'):
        return False

    return True