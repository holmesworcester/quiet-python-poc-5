"""
Queries for user event type.
"""
from core.db import ReadOnlyConnection
from typing import Dict, Any, List, Optional
import sqlite3
from core.queries import query


@query
def get(db: ReadOnlyConnection, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    List users visible to an identity in a network.

    Required params:
    - identity_id: Identity requesting the users
    - network_id: The network to list users for

    Optional params:
    - limit: Maximum number of users to return (default 100)
    - offset: Offset for pagination
    """
    identity_id = params.get('identity_id')
    if not identity_id:
        raise ValueError("identity_id is required for get_users")

    network_id = params.get('network_id')
    if not network_id:
        raise ValueError("network_id is required")
    
    limit = params.get('limit', 100)
    offset = params.get('offset', 0)
    
    # Only show users if the identity has access to the network
    # TODO: Properly check network membership
    cursor = db.execute(
        """
        SELECT u.*, i.name
        FROM users u
        LEFT JOIN core_identities i ON u.peer_id = i.identity_id
        WHERE u.network_id = ?
        AND EXISTS (
            SELECT 1 FROM core_identities i2
            WHERE i2.identity_id = ?
        )
        ORDER BY u.joined_at DESC
        LIMIT ? OFFSET ?
        """,
        (network_id, identity_id, limit, offset)
    )
    
    users = []
    for row in cursor:
        users.append(dict(row))
    
    return users


@query
def get_user(db: ReadOnlyConnection, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
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
        LEFT JOIN core_identities i ON u.peer_id = i.identity_id
        WHERE u.user_id = ?
        """,
        (user_id,)
    )
    
    row = cursor.fetchone()
    return dict(row) if row else None


@query
def get_user_by_peer_id(db: ReadOnlyConnection, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
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
        LEFT JOIN core_identities i ON u.peer_id = i.identity_id
        WHERE u.peer_id = ? AND u.network_id = ?
        ORDER BY u.joined_at DESC
        LIMIT 1
        """,
        (peer_id, network_id)
    )
    
    row = cursor.fetchone()
    return dict(row) if row else None


@query
def count_users(db: ReadOnlyConnection, params: Dict[str, Any]) -> int:
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


@query
def is_user_in_network(db: ReadOnlyConnection, params: Dict[str, Any]) -> bool:
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