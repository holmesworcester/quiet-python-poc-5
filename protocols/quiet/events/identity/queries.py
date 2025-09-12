"""
Query functions for identity events.
"""
from typing import Dict, Any, Optional, List
from core.query import query, ReadOnlyConnection


@query
def get_identity(db: ReadOnlyConnection, identity_id: str) -> Optional[Dict[str, Any]]:
    """Get an identity by ID."""
    cursor = db.cursor()
    cursor.execute("""
        SELECT identity_id, network_id, name, public_key, private_key, created_at
        FROM identities
        WHERE identity_id = ?
    """, (identity_id,))
    
    row = cursor.fetchone()
    if row:
        return dict(row)
    return None


@query
def get_identities_for_network(db: ReadOnlyConnection, network_id: str) -> List[Dict[str, Any]]:
    """Get all identities for a network."""
    cursor = db.cursor()
    cursor.execute("""
        SELECT identity_id, network_id, name, created_at
        FROM identities
        WHERE network_id = ?
        ORDER BY created_at DESC
    """, (network_id,))
    
    return [dict(row) for row in cursor.fetchall()]


@query
def get_user_by_id(db: ReadOnlyConnection, user_id: str) -> Optional[Dict[str, Any]]:
    """Get a user by ID (public view, no private key)."""
    cursor = db.cursor()
    cursor.execute("""
        SELECT user_id, network_id, name, peer_id
        FROM users
        WHERE user_id = ?
    """, (user_id,))
    
    row = cursor.fetchone()
    if row:
        return dict(row)
    return None


@query
def get_users_for_network(db: ReadOnlyConnection, network_id: str) -> List[Dict[str, Any]]:
    """Get all users for a network (public view)."""
    cursor = db.cursor()
    cursor.execute("""
        SELECT user_id, network_id, name, peer_id
        FROM users
        WHERE network_id = ?
        ORDER BY name
    """, (network_id,))
    
    return [dict(row) for row in cursor.fetchall()]