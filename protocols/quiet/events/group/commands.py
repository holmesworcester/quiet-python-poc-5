"""
Commands for group event type.
"""
import time
import sqlite3
from typing import Dict, Any, List
from core.core_types import command, response_handler


@command
def create_group(params: Dict[str, Any]) -> List[dict[str, Any]]:
    """
    Create a new group.

    Returns a list of envelopes with group event and member event for the creator.
    """
    # Extract parameters with sensible defaults
    name = params.get('name', '') or 'unnamed-group'
    network_id = params.get('network_id', '') or 'dummy-network-id'
    identity_id = params.get('identity_id', '') or 'dummy-identity-id'
    
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
    
    # Create member event for the creator
    member_event: Dict[str, Any] = {
        'type': 'member',
        'group_id': '',  # Will be filled when group is created
        'user_id': identity_id,
        'added_by': identity_id,
        'network_id': network_id,
        'created_at': int(time.time() * 1000),
        'signature': ''  # Will be filled by sign handler
    }

    # Return group and member event envelopes
    return [
        {
            'event_plaintext': event,
            'event_type': 'group',
            'self_created': True,
            'peer_id': identity_id,
            'network_id': network_id,
            'deps': []  # Group creation doesn't depend on other events
        },
        {
            'event_plaintext': member_event,
            'event_type': 'member',
            'self_created': True,
            'peer_id': identity_id,
            'network_id': network_id,
            'deps': ['group:']  # Member depends on group existing
        }
    ]


@response_handler('create_group')
def create_group_response(stored_ids: Dict[str, str], params: Dict[str, Any], db: sqlite3.Connection) -> Dict[str, Any]:
    """
    Response handler for create_group command.
    Returns all groups in the network including the newly created one.
    """
    network_id = params.get('network_id', '')

    # Get the newly created group ID
    new_group_id = stored_ids.get('group', '')

    # Query all groups in the network
    cursor = db.execute("""
        SELECT group_id, name, creator_id, created_at
        FROM groups
        WHERE network_id = ?
        ORDER BY created_at DESC
    """, (network_id,))

    groups = []
    for row in cursor:
        groups.append({
            'group_id': row[0],
            'name': row[1],
            'creator_id': row[2],
            'created_at': row[3]
        })

    # Return standard response format with ids and data
    return {
        'ids': stored_ids,  # Contains 'group': group_id
        'data': {
            'group_id': new_group_id,
            'name': params.get('name', ''),
            'network_id': network_id,
            'creator_id': params.get('identity_id', ''),
            'groups': groups  # All groups in the network
        }
    }