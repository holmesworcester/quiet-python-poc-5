"""
Commands for address event type.
"""
import time
from typing import Dict, Any
from core.core_types import command


@command
def announce_address(params: Dict[str, Any]) -> dict[str, Any]:
    """
    Announce a network address for a peer.
    This allows other peers to find and connect to this peer.

    Returns an envelope with unsigned address event.
    """
    # Extract parameters
    peer_id = params.get('peer_id', '')  # The peer announcing its address
    user_id = params.get('user_id', '')  # The user account this peer represents
    address = params.get('address', '0.0.0.0')  # IP address or hostname
    port = params.get('port', 0)  # Port number
    network_id = params.get('network_id', '')

    # Create address event (unsigned)
    event: Dict[str, Any] = {
        'type': 'address',
        'address_id': '',  # Will be filled by handler as hash
        'peer_id': peer_id,
        'user_id': user_id,
        'address': address,
        'port': int(port),
        'network_id': network_id,
        'timestamp': int(time.time() * 1000),
        'signature': ''  # Will be filled by sign handler
    }

    # Create envelope
    envelope: dict[str, Any] = {
        'event_plaintext': event,
        'event_type': 'address',
        'self_created': True,
        'peer_id': peer_id,  # The peer signs this
        'network_id': network_id,
        'deps': [
            f"peer:{peer_id}",  # Peer must exist
            f"user:{user_id}"  # User account must exist
        ]
    }

    return envelope