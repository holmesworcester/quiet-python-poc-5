"""
Commands for group event type.
"""
import time
import sqlite3
from typing import Dict, Any, List
from core.core_types import command, response_handler


@command
def create_group(params: Dict[str, Any]) -> dict[str, Any]:
    """
    Create a new group.

    Returns an envelope with unsigned group event.
    """
    # Extract and validate required parameters
    name = params.get('name', '')
    if not name:
        raise ValueError("name is required")

    network_id = params.get('network_id', '')
    if not network_id:
        raise ValueError("network_id is required")

    identity_id = params.get('identity_id', '')
    if not identity_id:
        raise ValueError("identity_id is required")
    
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
    envelope: dict[str, Any] = {
        'event_plaintext': event,
        'event_type': 'group',
        'self_created': True,
        'peer_id': identity_id,
        'network_id': network_id,
        'deps': []  # Group creation doesn't depend on other events
    }
    
    return envelope