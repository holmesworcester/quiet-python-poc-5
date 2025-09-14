"""
Commands for group event type.
"""
import time
from typing import Dict, Any
from core.types import Envelope, command


@command
def create_group(params: Dict[str, Any]) -> Envelope:
    """
    Create a new group.
    
    Returns an envelope with unsigned group event.
    """
    # Extract parameters
    name = params.get('name', '')
    network_id = params.get('network_id', '')
    identity_id = params.get('identity_id', '')
    
    # Create group event (unsigned)
    event: Dict[str, Any] = {
        'type': 'group',
        'group_id': '',  # Will be filled by encrypt handler
        'name': name,
        'network_id': network_id,
        'creator_id': identity_id,
        'created_at': int(time.time() * 1000),
        'signature': ''  # Will be filled by sign handler
    }
    
    # Create envelope
    envelope: Envelope = {
        'event_plaintext': event,
        'event_type': 'group',
        'self_created': True,
        'peer_id': identity_id,
        'network_id': network_id,
        'deps': []  # Group creation doesn't depend on other events
    }
    
    return envelope