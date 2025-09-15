"""
Queries for group event type.
"""
from core.db import ReadOnlyConnection
from typing import Dict, Any, List
import sqlite3
from core.queries import query
import json


@query
def get(db: ReadOnlyConnection, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    List groups visible to an identity.

    Required params:
    - identity_id: Identity requesting the groups

    Optional params:
    - network_id: Filter by network
    - user_id: Filter by groups the user is member of
    """
    # identity_id is required for access control
    identity_id = params.get('identity_id')
    if not identity_id:
        raise ValueError("identity_id is required for get_groups")

    network_id = params.get('network_id')
    user_id = params.get('user_id')

    # Only show groups the identity has access to
    # TODO: Check group membership properly
    query = """
        SELECT * FROM groups
        WHERE EXISTS (
            SELECT 1 FROM identities i
            WHERE i.identity_id = ?
        )
    """
    query_params = [identity_id]
    
    if network_id:
        query += " AND network_id = ?"
        query_params.append(network_id)
    
    if user_id:
        # Filter by groups the user is a member of
        query = """
        SELECT g.* FROM groups g
        JOIN group_members gm ON g.group_id = gm.group_id
        WHERE gm.user_id = ?
        AND EXISTS (
            SELECT 1 FROM identities i
            WHERE i.identity_id = ?
        )
        """
        query_params = [user_id, identity_id]
        if network_id:
            query += " AND g.network_id = ?"
            query_params.append(network_id)
    
    query += " ORDER BY created_at DESC"
    
    cursor = db.execute(query, tuple(query_params))
    
    groups = []
    for row in cursor:
        group = dict(row)
        # Parse permissions JSON
        if group.get('permissions'):
            group['permissions'] = json.loads(group['permissions'])
        groups.append(group)
    
    return groups