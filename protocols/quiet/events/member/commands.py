"""
Commands for member event type.
"""
import time
import sqlite3
from typing import Dict, Any, List
from core.core_types import command, response_handler
from protocols.quiet.client import CreateMemberParams, CreateMemberResult


@command(param_type=CreateMemberParams, result_type=CreateMemberResult)
def create_member(params: Dict[str, Any]) -> dict[str, Any]:
    """
    Create a group member.

    Returns an envelope with unsigned member event.
    """
    # Extract and validate parameters
    group_id = params.get('group_id', '')
    if not group_id:
        raise ValueError("group_id is required")

    user_id = params.get('user_id', '')
    if not user_id:
        raise ValueError("user_id is required")

    identity_id = params.get('identity_id', '')
    if not identity_id:
        raise ValueError("identity_id is required")

    network_id = params.get('network_id', '')
    if not network_id:
        raise ValueError("network_id is required")
    
    # Create member event (unsigned)
    event: Dict[str, Any] = {
        'type': 'member',
        'group_id': group_id,
        'user_id': user_id,
        'added_by': identity_id,
        'network_id': network_id,
        'created_at': int(time.time() * 1000),
        'signature': ''  # Will be filled by sign handler
    }
    
    # Create envelope
    envelope: dict[str, Any] = {
        'event_plaintext': event,
        'event_type': 'member',
        'self_created': True,
        'identity_id': identity_id,  # Core identity that will sign this
        'network_id': network_id,
        'deps': [f"group:{group_id}", f"user:{user_id}"]  # Depends on group and user existing
    }
    
    return envelope


@response_handler('create_member')
def create_member_response(stored_ids: Dict[str, str], params: Dict[str, Any], db: sqlite3.Connection) -> Dict[str, Any]:
    """
    Response handler for create_member command.
    Returns all group members including the newly added one.
    """
    group_id = params.get('group_id', '')

    # Query all members of the group
    cursor = db.execute("""
        SELECT u.user_id, u.name, u.peer_id, u.created_at
        FROM users u
        JOIN group_members gm ON u.user_id = gm.user_id
        WHERE gm.group_id = ?
        ORDER BY u.created_at DESC
    """, (group_id,))

    members = []
    for row in cursor:
        members.append({
            'user_id': row[0],
            'name': row[1],
            'peer_id': row[2],
            'created_at': row[3]
        })

    # Return response matching OpenAPI spec
    return {
        'added': 'member' in stored_ids,
        'group_id': group_id,
        'members': members,
        'member_count': len(members)
    }
