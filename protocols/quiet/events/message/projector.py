"""
Projector for message events.
"""
from typing import List, Any
from core.core_types import projector
from protocols.quiet.events import MessageEventData


@projector
def project(envelope: dict[str, Any]) -> List[dict[str, Any]]:
    """
    Project message event to state.
    Returns deltas to apply.
    """
    # Check required fields
    if 'event_plaintext' not in envelope or not envelope.get('validated'):
        return []
    
    event_data = envelope['event_plaintext']
    
    # Extract fields - we know this is a MessageEventData
    message_id = event_data['message_id']
    channel_id = event_data['channel_id']
    group_id = event_data['group_id']
    network_id = event_data['network_id']
    author_id = event_data['peer_id']  # Using peer_id as per MessageEventData
    content = event_data['content']
    created_at = event_data['created_at']
    
    # Return deltas for creating a message
    deltas: List[dict[str, Any]] = [
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