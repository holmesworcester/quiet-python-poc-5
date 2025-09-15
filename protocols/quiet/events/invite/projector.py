"""
Projector for invite events.
"""
from typing import Dict, Any, List


def project(envelope: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Project an invite event into the invites table.

    Returns a list of deltas.
    """
    event_data = envelope.get('event_plaintext', {})
    # Return delta for creating an invite
    deltas = [
        {
            'op': 'insert',
            'table': 'invites',
            'data': {
                'invite_id': event_data['invite_id'],
                'invite_pubkey': event_data['invite_pubkey'],
                'network_id': event_data['network_id'],
                'group_id': event_data['group_id'],
                'inviter_id': event_data['inviter_id'],
                'created_at': event_data['created_at']
            }
        }
    ]

    return deltas