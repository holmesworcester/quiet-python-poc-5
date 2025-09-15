"""
Projector for address events.
"""
from typing import Dict, Any, List


def project(envelope: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Project an address event into the addresses table.

    Address events are ephemeral - they update existing records
    for the same peer if they exist.

    Returns a list of deltas.
    """
    event_data = envelope.get('event_plaintext', {})

    # Return delta for upserting address record
    # We want the latest address for each peer
    deltas = [
        {
            'op': 'upsert',
            'table': 'addresses',
            'key': {'peer_id': event_data['peer_id']},  # Update by peer_id
            'data': {
                'address_id': envelope.get('event_id', ''),  # Hash of event
                'peer_id': event_data['peer_id'],
                'user_id': event_data['user_id'],
                'address': event_data['address'],
                'port': event_data['port'],
                'network_id': event_data['network_id'],
                'last_seen': event_data['timestamp']
            }
        }
    ]

    return deltas