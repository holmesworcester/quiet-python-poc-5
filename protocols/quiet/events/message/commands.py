"""
Commands for message event type.
"""
import time
from typing import Dict, Any
from core.crypto import hash as generate_hash
from core.types import Envelope, command
from protocols.quiet.events import CreateMessageParams


@command
def create_message(params: Dict[str, Any]) -> Envelope:
    """
    Create a new message in a channel.
    
    Required params:
    - content: Message content
    - channel_id: Channel to send message to
    - identity_id: Identity sending the message
    
    Note: This command validates dependencies exist but doesn't
    include their data - that's handled by resolve_deps handler.
    """
    # Validate parameters
    try:
        cmd_params = CreateMessageParams(
            content=params['content'],
            channel_id=params['channel_id'],
            identity_id=params['identity_id']
        )
    except (KeyError, TypeError) as e:
        raise ValueError(f"Invalid parameters: {e}")
    
    # Commands don't access DB - just declare dependencies
    # The actual validation happens in resolve_deps and validate handlers
    peer_id = cmd_params.identity_id
    
    # Generate message_id
    created_at = int(time.time() * 1000)
    message_id = generate_hash(f"{cmd_params.content}:{peer_id}:{created_at}".encode()).hex()
    
    # Create message event (unsigned)
    event: dict[str, Any] = {
        'type': 'message',
        'message_id': message_id,
        'channel_id': cmd_params.channel_id,
        'group_id': '',  # Will be filled by resolve_deps
        'network_id': '',  # Will be filled by resolve_deps
        'peer_id': peer_id,
        'content': cmd_params.content,
        'created_at': created_at,
        'signature': ''  # Will be filled by sign handler
    }
    
    # Create envelope
    envelope: Envelope = {
        'event_plaintext': event,
        'event_type': 'message',
        'self_created': True,
        'peer_id': peer_id,
        'deps': [
            f"identity:{cmd_params.identity_id}",  # Need identity for signing
            f"channel:{cmd_params.channel_id}"  # Need channel for group_id/network_id
        ]
    }
    
    return envelope