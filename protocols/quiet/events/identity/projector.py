"""
Projector for identity events.
"""
from typing import Dict, Any, List
from core.types import Envelope, Delta, projector, ValidatedEnvelope, cast_envelope
from protocols.quiet.events import IdentityEventData


@projector
def project(envelope: Envelope) -> List[Delta]:
    """
    Project identity event to state.
    Returns deltas to apply.
    """
    # Runtime validation
    try:
        validated_env = cast_envelope(envelope, ValidatedEnvelope)
    except TypeError:
        return []
    
    event_data = validated_env['event_plaintext']
    
    # Type narrowing - we know this is an IdentityEventData
    peer_id = event_data['peer_id']
    network_id = event_data['network_id']
    created_at = event_data['created_at']
    name = event_data.get('name', 'User')  # Use provided name or default
    
    # Return deltas for creating a peer (not user - that's handled by user events)
    deltas: List[Delta] = [
        # Maintain the infrastructure peers table
        {
            'op': 'insert',
            'table': 'peers',
            'data': {
                'peer_id': peer_id,
                'network_id': network_id,
                'public_key': bytes.fromhex(peer_id),
                'added_at': created_at
            },
            'where': {}
        }
    ]
    
    # If this identity was created via invite, mark the invite as used
    if 'invite_code' in event_data:
        deltas.append({
            'op': 'update',
            'table': 'invites',
            'where': {'invite_code': event_data['invite_code']},
            'data': {
                'used': 1,
                'used_by': peer_id,
                'used_at': created_at
            }
        })
    
    # Store the identity with private key in local storage
    if 'local_metadata' in envelope:
        deltas.append({
            'op': 'insert',
            'table': 'identities',
            'data': {
                'identity_id': peer_id,
                'network_id': network_id,
                'name': name,
                'private_key': envelope['local_metadata'].get('private_key'),
                'public_key': envelope['local_metadata'].get('public_key'),
                'created_at': created_at
            },
            'where': {}
        })
    
    return deltas