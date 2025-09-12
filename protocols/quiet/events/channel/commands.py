"""
Commands for channel event type.
"""
import time
from typing import Dict, Any, List
import sqlite3
from core.crypto import hash as generate_hash


def create_channel(params: Dict[str, Any], db: sqlite3.Connection) -> List[Dict[str, Any]]:
    """
    Create a new channel within a group.
    
    Required params:
    - name: Channel name
    - group_id: Group this channel belongs to
    - identity_id: Identity creating the channel
    
    Optional params:
    - description: Channel description
    """
    name = params.get('name')
    group_id = params.get('group_id')
    identity_id = params.get('identity_id')
    description = params.get('description', '')
    
    if not name or not group_id or not identity_id:
        raise ValueError("name, group_id, and identity_id are required")
    
    # Get identity info
    cursor = db.execute(
        "SELECT identity_id as peer_id FROM identities WHERE identity_id = ?",
        (identity_id,)
    )
    identity = cursor.fetchone()
    if not identity:
        raise ValueError(f"Identity not found: {identity_id}")
    
    peer_id = identity['peer_id']
    
    # Check if user is member of the group
    cursor = db.execute(
        "SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?",
        (group_id, peer_id)
    )
    if not cursor.fetchone():
        raise ValueError("User is not a member of the group")
    
    # Get group's network_id
    cursor = db.execute(
        "SELECT network_id FROM groups WHERE group_id = ?",
        (group_id,)
    )
    group = cursor.fetchone()
    if not group:
        raise ValueError(f"Group not found: {group_id}")
    
    network_id = group['network_id']
    
    # Generate channel_id
    created_at = int(time.time() * 1000)
    channel_id = generate_hash(f"{name}:{group_id}:{peer_id}:{created_at}".encode()).hex()
    
    # Create channel event (unsigned)
    event = {
        'type': 'channel',
        'channel_id': channel_id,
        'group_id': group_id,
        'name': name,
        'network_id': network_id,
        'creator_id': peer_id,
        'created_at': created_at,
        'description': description
    }
    
    # Create envelope
    envelope = {
        'event_plaintext': event,
        'event_type': 'channel',
        'self_created': True,
        'peer_id': peer_id,
        'network_id': network_id,
        'group_id': group_id,
        'deps': [group_id]  # Channel depends on the group existing
    }
    
    return [envelope]