"""
Commands for network event type.
"""
import time
from typing import Dict, Any, List
from core.core_types import command
from protocols.quiet.client import CreateNetworkParams, CommandResponse


@command(param_type=CreateNetworkParams, result_type=CommandResponse)
def create_network(params: Dict[str, Any]) -> dict[str, Any]:
    """
    Create a new network.

    Requires peer_id of the creator (peer must be created first).
    """
    # Extract and validate parameters
    name = params.get('name', '')
    if not name:
        raise ValueError("name is required")

    # Backward-compat: some tests pass identity_id as the creating actor
    peer_id = params.get('peer_id') or params.get('identity_id')
    if not peer_id:
        raise ValueError("peer_id is required - create a peer first")

    # Create network event
    network_event: Dict[str, Any] = {
        'type': 'network',
        'network_id': '',  # Will be filled by crypto handler
        'name': name,
        'creator_id': peer_id,  # Creator is identified by their peer
        'created_at': int(time.time() * 1000),
        'signature': ''  # Will be filled by sign handler
    }

    return {
        'event_plaintext': network_event,
        'event_type': 'network',
        'self_created': True,
        'peer_id': peer_id,  # Peer that's creating this
        'network_id': '',  # Will be filled by crypto handler
        'deps': [f'peer:{peer_id}']  # Network depends on peer existing
    }
