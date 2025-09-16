"""
Queries for group event type.
"""
from core.db import ReadOnlyConnection
from typing import Dict, Any, List
import sqlite3
from core.queries import query
from protocols.quiet.client import GroupGetParams, GroupRecord
import json


@query(param_type=GroupGetParams, result_type=list[GroupRecord])
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
    owner_id = params.get('owner_id')
    user_id = params.get('user_id')

    # Only show groups the identity has access to
    # TODO: Check group membership properly
    base_select = "SELECT g.*, COALESCE((SELECT COUNT(*) FROM group_members gm WHERE gm.group_id = g.group_id), 0) AS member_count FROM groups g"
    query = f"""
        {base_select}
        WHERE EXISTS (
            SELECT 1 FROM core_identities i
            WHERE i.identity_id = ?
        )
    """
    query_params = [identity_id]
    
    if network_id:
        query += " AND g.network_id = ?"
        query_params.append(network_id)
    if owner_id:
        query += " AND g.owner_id = ?"
        query_params.append(owner_id)
    
    if user_id:
        # Filter by groups the user is a member of
        query = f"""
        SELECT g.*, COALESCE((SELECT COUNT(*) FROM group_members gm2 WHERE gm2.group_id = g.group_id), 0) AS member_count FROM groups g
        JOIN group_members gm ON g.group_id = gm.group_id
        WHERE gm.user_id = ?
        AND EXISTS (
            SELECT 1 FROM core_identities i
            WHERE i.identity_id = ?
        )
        """
        query_params = [user_id, identity_id]
        if network_id:
            query += " AND g.network_id = ?"
            query_params.append(network_id)
        if owner_id:
            query += " AND g.owner_id = ?"
            query_params.append(owner_id)
    
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
