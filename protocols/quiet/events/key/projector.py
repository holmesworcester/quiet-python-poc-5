"""
Projector for key events.
"""
from typing import Dict, Any, List


def project(envelope: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Project key event to state.
    Returns deltas to apply.
    """
    event_data = envelope.get('event_plaintext', {})
    key_id = event_data['key_id']
    group_id = event_data['group_id']
    peer_id = event_data['peer_id']
    network_id = event_data['network_id']
    created_at = event_data['created_at']
    
    # Note: We cannot check if we can unseal the key here anymore
    # That logic should be handled elsewhere in the processing pipeline
    # For now, we'll just store the key metadata
    
    deltas = []
    
    # Store key metadata
    deltas.append({
        'op': 'insert',
        'table': 'group_keys',
        'data': {
            'key_id': key_id,
            'group_id': group_id,
            'peer_id': peer_id,
            'created_at': created_at
        }
    })
    
    return deltas