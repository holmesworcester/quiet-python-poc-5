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
    # Extract parameters - frontend provides peer_id
    name = params.get('name', '') or 'unnamed-group'
    network_id = params.get('network_id', '') or 'dummy-network-id'
    peer_id = params.get('peer_id', '')  # Frontend provides peer_id

    if not peer_id:
        raise ValueError("peer_id is required for create_group")

    # Create group event (unsigned)
    event: Dict[str, Any] = {
        'type': 'group',
        'group_id': '',  # Will be filled by encrypt handler
        'name': name,
        'network_id': network_id,
        'creator_id': peer_id,  # Creator is identified by their peer event
        'created_at': int(time.time() * 1000),
        'signature': ''  # Will be filled by sign handler
    }
    
    # Create member event for the creator
    member_event: Dict[str, Any] = {
        'type': 'member',
        'group_id': '',  # Will be filled when group is created
        'user_id': peer_id,  # User is identified by their peer event
        'added_by': peer_id,  # Added by themselves
        'network_id': network_id,
        'created_at': int(time.time() * 1000),
        'signature': ''  # Will be filled by sign handler
    }

    # Return only group event envelope (member events are created separately)
    return [
        {
            'event_plaintext': event,
            'event_type': 'group',
            'self_created': True,
            'peer_id': peer_id,  # Identifies who's creating this
            'network_id': network_id,
            'deps': []  # Group creation doesn't depend on other events
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