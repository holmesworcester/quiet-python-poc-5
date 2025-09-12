"""
Queries for user event type.
"""
from typing import Dict, Any, List, Optional
import sqlite3


def list_users(params: Dict[str, Any], db: sqlite3.Connection) -> List[Dict[str, Any]]:
    """
    List all users in a network.
    
    Required params:
    - network_id: The network to list users for
    
    Optional params:
    - limit: Maximum number of users to return (default 100)
    - offset: Offset for pagination
    """
    network_id = params.get('network_id')
    if not network_id:
        raise ValueError("network_id is required")
    
    limit = params.get('limit', 100)
    offset = params.get('offset', 0)
    
    cursor = db.execute(
        """
        SELECT u.*, i.name
        FROM users u
        LEFT JOIN identities i ON u.peer_id = i.identity_id
        WHERE u.network_id = ?
        ORDER BY u.joined_at DESC
        LIMIT ? OFFSET ?
        """,
        (network_id, limit, offset)
    )
    
    users = []
    for row in cursor:
        users.append(dict(row))
    
    return users


def get_user(params: Dict[str, Any], db: sqlite3.Connection) -> Optional[Dict[str, Any]]:
    """
    Get a specific user by ID.
    
    Required params:
    - user_id: The user to look up
    """
    user_id = params.get('user_id')
    
    if not user_id:
        raise ValueError("user_id is required")
    
    cursor = db.execute(
        """
        SELECT u.*, i.name
        FROM users u
        LEFT JOIN identities i ON u.peer_id = i.identity_id
        WHERE u.user_id = ?
        """,
        (user_id,)
    )
    
    row = cursor.fetchone()
    return dict(row) if row else None


def get_user_by_peer_id(params: Dict[str, Any], db: sqlite3.Connection) -> Optional[Dict[str, Any]]:
    """
    Get a user by their peer ID in a specific network.
    
    Required params:
    - peer_id: The peer ID to look up
    - network_id: The network to search in
    """
    peer_id = params.get('peer_id')
    network_id = params.get('network_id')
    
    if not peer_id or not network_id:
        raise ValueError("peer_id and network_id are required")
    
    cursor = db.execute(
        """
        SELECT u.*, i.name
        FROM users u
        LEFT JOIN identities i ON u.peer_id = i.identity_id
        WHERE u.peer_id = ? AND u.network_id = ?
        ORDER BY u.joined_at DESC
        LIMIT 1
        """,
        (peer_id, network_id)
    )
    
    row = cursor.fetchone()
    return dict(row) if row else None


def count_users(params: Dict[str, Any], db: sqlite3.Connection) -> int:
    """
    Count users in a network.
    
    Required params:
    - network_id: The network to count users for
    """
    network_id = params.get('network_id')
    if not network_id:
        raise ValueError("network_id is required")
    
    cursor = db.execute(
        """
        SELECT COUNT(*) as count
        FROM users
        WHERE network_id = ?
        """,
        (network_id,)
    )
    
    row = cursor.fetchone()
    return row['count'] if row else 0


def is_user_in_network(params: Dict[str, Any], db: sqlite3.Connection) -> bool:
    """
    Check if a peer has joined a network as a user.
    
    Required params:
    - peer_id: The peer to check
    - network_id: The network to check
    """
    peer_id = params.get('peer_id')
    network_id = params.get('network_id')
    
    if not peer_id or not network_id:
        raise ValueError("peer_id and network_id are required")
    
    cursor = db.execute(
        """
        SELECT 1 FROM users 
        WHERE peer_id = ? AND network_id = ?
        """,
        (peer_id, network_id)
    )
    
    return cursor.fetchone() is not None