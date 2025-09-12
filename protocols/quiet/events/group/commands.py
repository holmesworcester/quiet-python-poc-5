"""
Commands for group event type.
"""
import time
from typing import Dict, Any, List
import sqlite3
from core.crypto import hash as generate_hash


def create_group(params: Dict[str, Any], db: sqlite3.Connection) -> List[Dict[str, Any]]:
    """
    Create a new group.
    
    Required params:
    - name: Group name
    - network_id: Network this group belongs to
    - identity_id: Identity creating the group
    """
    name = params.get('name')
    network_id = params.get('network_id')
    identity_id = params.get('identity_id')
    
    if not name or not network_id or not identity_id:
        raise ValueError("name, network_id, and identity_id are required")
    
    # Get identity info
    cursor = db.execute(
        "SELECT identity_id as peer_id FROM identities WHERE identity_id = ?",
        (identity_id,)
    )
    identity = cursor.fetchone()
    if not identity:
        raise ValueError(f"Identity not found: {identity_id}")
    
    peer_id = identity['peer_id']
    
    # Generate group_id from hash of name + creator + timestamp
    created_at = int(time.time() * 1000)
    group_id = generate_hash(f"{name}:{peer_id}:{created_at}".encode()).hex()
    
    # Create group event (unsigned)
    event = {
        'type': 'group',
        'group_id': group_id,
        'name': name,
        'network_id': network_id,
        'creator_id': peer_id,
        'created_at': created_at,
        'permissions': {
            'invite': ['creator', 'admin'],
            'remove': ['creator', 'admin'],
            'message': ['all']
        }
    }
    
    # Create envelope
    envelope = {
        'event_plaintext': event,
        'event_type': 'group',
        'self_created': True,
        'peer_id': peer_id,
        'network_id': network_id,
        'group_id': group_id,
        'deps': []  # Group creation doesn't depend on other events
    }
    
    return [envelope]