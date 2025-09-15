"""
Projector for identity events.
"""
from typing import Dict, Any, List
from core.core_types import projector
from protocols.quiet.events import IdentityEventData


@projector
def project(envelope: dict[str, Any]) -> List[dict[str, Any]]:
    """
    Project identity event to state.
    Identity events are local-only and don't get shared.
    Returns deltas to apply.
    """
    # Check required fields
    if 'event_plaintext' not in envelope:
        return []

    event_data = envelope['event_plaintext']

    # Identity events are local-only, store if we created it
    if not envelope.get('self_created') or 'secret' not in envelope:
        return []

    # Get fields from event
    identity_id = envelope.get('event_id')  # Pre-calculated hash
    network_id = event_data['network_id']
    created_at = event_data['created_at']
    name = event_data.get('name', 'User')
    public_key = event_data.get('public_key')

    # Store the identity with private key in local storage
    deltas = [
        {
            'op': 'insert',
            'table': 'identities',
            'data': {
                'identity_id': identity_id,
                'network_id': network_id,
                'name': name,
                'private_key': envelope['secret'].get('private_key'),
                'public_key': envelope['secret'].get('public_key') or public_key,
                'created_at': created_at
            },
            'where': {}
        }
    ]

    return deltas