"""
Commands for address event type.
"""
import time
from typing import Dict, Any, Optional
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
    ip = params.get('ip', '127.0.0.1')  # IP address
    port = params.get('port', 5000)  # Port number
    action = params.get('action', 'add')  # 'add' or 'remove'
    network_id = params.get('network_id', '')

    # Create address event (unsigned)
    event: Dict[str, Any] = {
        'type': 'address',
        'action': action,
        'peer_id': peer_id,
        'ip': ip,
        'port': int(port),
        'network_id': network_id,
        'timestamp_ms': int(time.time() * 1000),
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
        ]
    }

    return envelope


def create_address_add(peer_id: str, ip: str, port: int = 5000,
                      network_id: str = '', timestamp_ms: Optional[int] = None) -> Dict[str, Any]:
    """
    Create an address registration event.

    Args:
        peer_id: ID of the peer advertising this address
        ip: IP address
        port: Port number (default 5000)
        network_id: Network ID
        timestamp_ms: Timestamp in milliseconds

    Returns:
        Envelope for address registration
    """
    if timestamp_ms is None:
        timestamp_ms = int(time.time() * 1000)

    return announce_address({
        'peer_id': peer_id,
        'ip': ip,
        'port': port,
        'action': 'add',
        'network_id': network_id
    })


def create_address_remove(peer_id: str, ip: str, port: int = 5000,
                         network_id: str = '', timestamp_ms: Optional[int] = None) -> Dict[str, Any]:
    """
    Create an address deregistration event.

    Args:
        peer_id: ID of the peer removing this address
        ip: IP address
        port: Port number (default 5000)
        network_id: Network ID
        timestamp_ms: Timestamp in milliseconds

    Returns:
        Envelope for address deregistration
    """
    if timestamp_ms is None:
        timestamp_ms = int(time.time() * 1000)

    return announce_address({
        'peer_id': peer_id,
        'ip': ip,
        'port': port,
        'action': 'remove',
        'network_id': network_id
    })