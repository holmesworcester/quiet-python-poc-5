"""
Commands for peer event type.
"""
import time
from typing import Dict, Any
from core.core_types import command


@command
def create_peer(params: Dict[str, Any]) -> dict[str, Any]:
    """
    Create a peer event for an identity.

    This should be called before creating or joining a network.
    The peer represents an identity's presence in the protocol.
    """
    identity_id = params.get('identity_id')
    if not identity_id:
        raise ValueError("identity_id is required")

    username = params.get('username', 'User')

    # Get the public key from core identity
    from core.identity import get_identity
    db = params.get('_db')
    identity = get_identity(identity_id, db=db)
    if not identity:
        raise ValueError(f"Identity {identity_id} not found")

    # Create peer event
    peer_event: Dict[str, Any] = {
        'type': 'peer',
        'peer_id': '',  # Will be filled by crypto handler
        'public_key': identity.public_key.hex(),
        'identity_id': identity_id,
        'username': username,
        'created_at': int(time.time() * 1000),
        'signature': ''  # Will be filled by sign handler
    }

    # Return the envelope for pipeline processing
    # The signature handler will use the public_key in the peer event to find the identity for signing
    # The real peer_id will be generated as the event hash by the crypto handler
    return {
        'event_plaintext': peer_event,
        'event_type': 'peer',
        'self_created': True,
        'deps': []  # Peer creation has no dependencies
    }