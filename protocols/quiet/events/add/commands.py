"""
Commands for add event type.
"""
import time
from typing import Dict, Any, List
import sqlite3


def create_add(params: Dict[str, Any], db: sqlite3.Connection) -> List[Dict[str, Any]]:
    """
    Add a user to a group.
    
    Params:
    - group_id: The group to add the user to
    - user_id: The user to add
    - identity_id: The identity performing the action
    - network_id: The network this is happening in
    
    Returns a list of envelopes to process.
    """
    if 'group_id' not in params:
        raise ValueError("group_id is required")
    if 'user_id' not in params:
        raise ValueError("user_id is required")
    if 'identity_id' not in params:
        raise ValueError("identity_id is required")
    if 'network_id' not in params:
        raise ValueError("network_id is required")
    
    # Get identity info
    cursor = db.execute(
        "SELECT identity_id as peer_id FROM identities WHERE identity_id = ?",
        (params['identity_id'],)
    )
    identity = cursor.fetchone()
    if not identity:
        raise ValueError(f"Identity not found: {params['identity_id']}")
    
    peer_id = identity['peer_id']
    
    # Check if the adder is a member of the group
    cursor = db.execute(
        "SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?",
        (params['group_id'], peer_id)
    )
    if not cursor.fetchone():
        raise ValueError("User is not a member of the group")
    
    # TODO: Check permissions - who can add members to groups
    
    # Create add event (unsigned)
    event = {
        'type': 'add',
        'group_id': params['group_id'],
        'user_id': params['user_id'],
        'added_by': peer_id,
        'network_id': params['network_id'],
        'created_at': int(time.time() * 1000)
    }
    
    # Return the event as an envelope
    envelope = {
        'event_plaintext': event,
        'event_type': 'add',
        'self_created': True,
        'peer_id': peer_id,
        'network_id': params['network_id'],
        'deps': [params['group_id'], params['user_id']]  # Depends on group and user existing
    }
    
    return [envelope]