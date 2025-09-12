"""
Projector for user events.
"""
from typing import Dict, Any, List


def project(envelope: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Project user event to state.
    
    User events represent a peer joining the network and establish
    their initial presence (even if offline).
    
    Returns deltas to apply.
    """
    event_data = envelope.get('event_plaintext', {})
    user_id = event_data['user_id']
    peer_id = event_data['peer_id']
    network_id = event_data['network_id']
    address = event_data['address']
    port = event_data['port']
    created_at = event_data['created_at']
    
    # Return deltas for creating user record
    deltas = [
        {
            'op': 'insert',
            'table': 'users',
            'data': {
                'user_id': user_id,
                'peer_id': peer_id,
                'network_id': network_id,
                'joined_at': created_at,
                'last_address': address,
                'last_port': port
            }
        }
    ]
    
    return deltas