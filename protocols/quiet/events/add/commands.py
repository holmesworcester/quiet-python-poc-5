"""
Commands for add event type.
"""
import time
from typing import Dict, Any
from core.types import Envelope, command


@command
def create_add(params: Dict[str, Any]) -> Envelope:
    """
    Add a user to a group.
    
    Returns an envelope with unsigned add event.
    """
    # Extract parameters
    group_id = params.get('group_id', '')
    user_id = params.get('user_id', '')
    identity_id = params.get('identity_id', '')
    network_id = params.get('network_id', '')
    
    # Create add event (unsigned)
    event: Dict[str, Any] = {
        'type': 'add',
        'group_id': group_id,
        'user_id': user_id,
        'added_by': identity_id,
        'network_id': network_id,
        'created_at': int(time.time() * 1000),
        'signature': ''  # Will be filled by sign handler
    }
    
    # Create envelope
    envelope: Envelope = {
        'event_plaintext': event,
        'event_type': 'add',
        'self_created': True,
        'peer_id': identity_id,
        'network_id': network_id,
        'deps': [f"group:{group_id}", f"user:{user_id}"]  # Depends on group and user existing
    }
    
    return envelope