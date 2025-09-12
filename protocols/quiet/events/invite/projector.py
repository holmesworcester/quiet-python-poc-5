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
                'invite_code': event_data['invite_code'],
                'network_id': event_data['network_id'],
                'created_by': event_data['inviter_id'],
                'created_at': event_data['created_at'],
                'expires_at': event_data['expires_at'],
                'used': 0,
                'used_by': None,
                'used_at': None
            }
        }
    ]
    
    return deltas