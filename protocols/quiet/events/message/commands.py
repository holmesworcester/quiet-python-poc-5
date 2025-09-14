"""
Commands for message event type.
"""
import time
from typing import Dict, Any
from core.types import Envelope, command


@command
def create_message(params: Dict[str, Any]) -> Envelope:
    """
    Create a new message in a channel.
    
    Returns an envelope with unsigned message event.
    """
    # Extract parameters
    content = params.get('content', '')
    channel_id = params.get('channel_id', '')
    identity_id = params.get('identity_id', '')
    
    # Create message event (unsigned)
    event: Dict[str, Any] = {
        'type': 'message',
        'message_id': '',  # Will be filled by encrypt handler
        'channel_id': channel_id,
        'group_id': '',  # Will be filled by resolve_deps
        'network_id': '',  # Will be filled by resolve_deps
        'peer_id': identity_id,
        'content': content,
        'created_at': int(time.time() * 1000),
        'signature': ''  # Will be filled by sign handler
    }
    
    # Create envelope
    envelope: Envelope = {
        'event_plaintext': event,
        'event_type': 'message',
        'self_created': True,
        'peer_id': identity_id,
        'network_id': '',  # Will be filled by resolve_deps  
        'deps': [
            f"identity:{identity_id}",  # Need identity for signing
            f"channel:{channel_id}"  # Need channel for group_id/network_id
        ]
    }
    
    return envelope