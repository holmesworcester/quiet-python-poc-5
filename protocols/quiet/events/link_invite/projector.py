"""
Projector for link_invite events.
"""
from typing import Dict, Any, List


def project(envelope: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Project a link_invite event into the link_invites table.

    Returns a list of deltas.
    """
    event_data = envelope.get('event_plaintext', {})

    # Return delta for creating a link_invite record
    deltas = [
        {
            'op': 'insert',
            'table': 'link_invites',
            'data': {
                'link_id': envelope.get('event_id', ''),  # Hash of event
                'peer_id': event_data['peer_id'],
                'user_id': event_data['user_id'],
                'network_id': event_data['network_id'],
                'created_at': event_data['created_at']
            }
        }
    ]

    return deltas