"""
Commands for link_invite event type.
"""
import time
from typing import Dict, Any
from core.core_types import command
from protocols.quiet.client import CreateLinkInviteParams, CommandResponse


@command(param_type=CreateLinkInviteParams, result_type=CommandResponse)
def create_link_invite(params: Dict[str, Any]) -> dict[str, Any]:
    """
    Create a link_invite event - the root event for linking a peer to a user.
    A separate link event will reference this link_invite.

    Returns an envelope with unsigned link_invite event.
    """
    # Extract parameters
    peer_id = params.get('peer_id', '')  # The peer to link
    user_id = params.get('user_id', '')  # The user account
    network_id = params.get('network_id', '')

    # Create link_invite event (unsigned)
    # Note: No link_id field - that's the hash of the event
    event: Dict[str, Any] = {
        'type': 'link_invite',
        'peer_id': peer_id,
        'user_id': user_id,
        'network_id': network_id,
        'created_at': int(time.time() * 1000),
        'signature': ''  # Will be filled by sign handler
    }

    # Create envelope
    # This should be signed by the peer being linked
    envelope: dict[str, Any] = {
        'event_plaintext': event,
        'event_type': 'link_invite',
        'self_created': True,
        'peer_id': peer_id,  # The peer signs this with their identity key
        'network_id': network_id,
        'deps': [
            f"peer:{peer_id}",  # Peer must exist
            f"user:{user_id}"   # User must exist and match
        ]
    }

    return envelope
