"""
Projector for message events.
"""
from typing import List
from core.types import Envelope, Delta, projector, ValidatedEnvelope, cast_envelope
from protocols.quiet.events import MessageEventData


@projector
def project(envelope: Envelope) -> List[Delta]:
    """
    Project message event to state.
    Returns deltas to apply.
    """
    # Runtime validation
    try:
        validated_env = cast_envelope(envelope, ValidatedEnvelope)
    except TypeError:
        return []
    
    event_data = validated_env['event_plaintext']
    
    # Extract fields - we know this is a MessageEventData
    message_id = event_data['message_id']
    channel_id = event_data['channel_id']
    group_id = event_data['group_id']
    network_id = event_data['network_id']
    author_id = event_data['peer_id']  # Using peer_id as per MessageEventData
    content = event_data['content']
    created_at = event_data['created_at']
    
    # Return deltas for creating a message
    deltas: List[Delta] = [
        {
            'op': 'insert',
            'table': 'messages',
            'data': {
                'message_id': message_id,
                'channel_id': channel_id,
                'group_id': group_id,
                'network_id': network_id,
                'author_id': author_id,
                'content': content,
                'created_at': created_at
            },
            'where': {}
        }
    ]
    
    return deltas