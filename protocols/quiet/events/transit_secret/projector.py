"""
Projector for transit secret events.
"""
from typing import Dict, Any, List


def project(envelope: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Project transit secret event to state.
    Transit secrets are primarily for sharing the key_id publicly.
    The actual secret is kept local.
    """
    event_data = envelope.get('event_plaintext', {})
    transit_key_id = event_data['transit_key_id']
    peer_id = event_data['peer_id']
    network_id = event_data['network_id']
    created_at = event_data['created_at']
    
    # Record that this peer has this transit key
    deltas = [
        {
            'op': 'insert',
            'table': 'peer_transit_keys',
            'data': {
                'transit_key_id': transit_key_id,
                'peer_id': peer_id,
                'network_id': network_id,
                'created_at': created_at
            }
        }
    ]
    
    return deltas