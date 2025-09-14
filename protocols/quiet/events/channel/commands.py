"""
Commands for channel event type.
"""
import time
from typing import Dict, Any
from core.types import Envelope, command


@command
def create_channel(params: Dict[str, Any]) -> Envelope:
    """
    Create a new channel within a group.
    
    Returns an envelope with unsigned channel event.
    """
    # Extract parameters
    name = params.get('name', '')
    group_id = params.get('group_id', '')
    identity_id = params.get('identity_id', '')
    network_id = params.get('network_id', '')
    
    # Create channel event (unsigned)
    event: Dict[str, Any] = {
        'type': 'channel',
        'channel_id': '',  # Will be filled by encrypt handler
        'group_id': group_id,
        'name': name,
        'network_id': network_id,
        'creator_id': identity_id,
        'created_at': int(time.time() * 1000),
        'signature': ''  # Will be filled by sign handler
    }
    
    # Create envelope
    envelope: Envelope = {
        'event_plaintext': event,
        'event_type': 'channel',
        'self_created': True,
        'peer_id': identity_id,
        'network_id': network_id,
        'deps': [f"group:{group_id}"]  # Channel depends on the group existing
    }
    
    return envelope