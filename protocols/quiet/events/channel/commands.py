"""
Commands for channel event type.
"""
import time
import sqlite3
from typing import Dict, Any, List
from core.core_types import command, response_handler


@command
def create_channel(params: Dict[str, Any]) -> dict[str, Any]:
    """
    Create a new channel within a group.

    Returns an envelope with unsigned channel event.
    """
    # Extract parameters with sensible defaults
    name = params.get('name', '') or 'unnamed-channel'
    group_id = params.get('group_id', '') or 'dummy-group-id'
    identity_id = params.get('identity_id', '') or 'dummy-identity-id'
    network_id = params.get('network_id', '') or 'dummy-network-id'
    
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
    envelope: dict[str, Any] = {
        'event_plaintext': event,
        'event_type': 'channel',
        'self_created': True,
        'peer_id': identity_id,
        'network_id': network_id,
        'deps': [f"group:{group_id}"]  # Channel depends on the group existing
    }
    
    return envelope


@response_handler('create_channel')
def create_channel_response(stored_ids: Dict[str, str], params: Dict[str, Any], db: sqlite3.Connection) -> Dict[str, Any]:
    """
    Response handler for create_channel command.
    Returns all channels in the group including the newly created one.
    """
    group_id = params.get('group_id', '')

    # Get the newly created channel ID
    new_channel_id = stored_ids.get('channel', '')

    # Query all channels in the group
    cursor = db.execute("""
        SELECT channel_id, name, group_id, created_at
        FROM channels
        WHERE group_id = ?
        ORDER BY created_at DESC
    """, (group_id,))

    channels = []
    for row in cursor:
        channels.append({
            'channel_id': row[0],
            'name': row[1],
            'group_id': row[2],
            'created_at': row[3]
        })

    # Return standard response format with ids and data
    return {
        'ids': stored_ids,  # Contains 'channel': channel_id
        'data': {
            'channel_id': new_channel_id,
            'name': params.get('name', ''),
            'group_id': group_id,
            'channels': channels  # All channels in the group
        }
    }