"""
Projector for identity events (local-only key storage).
"""
from typing import Dict, Any, List


def project(envelope: Dict[str, Any]) -> List[Dict[str, Any]]:
    event = envelope.get('event_plaintext', {})

    # Write to protocol identities table
    deltas = [
        {
            'op': 'insert',
            'table': 'identities',
            'data': {
                'identity_id': event['identity_id'],
                'name': event['name'],
                'public_key': event['public_key'],
                'private_key': bytes.fromhex(event['private_key']),
                'created_at': event['created_at'],
            }
        }
    ]

    return deltas

