"""
Queries for group event type.
"""
from typing import Dict, Any, List
import sqlite3
import json


def list_groups(params: Dict[str, Any], db: sqlite3.Connection) -> List[Dict[str, Any]]:
    """
    List all groups.
    
    Optional params:
    - network_id: Filter by network
    - user_id: Filter by groups the user is member of
    """
    network_id = params.get('network_id')
    user_id = params.get('user_id')
    
    query = "SELECT * FROM groups WHERE 1=1"
    query_params = []
    
    if network_id:
        query += " AND network_id = ?"
        query_params.append(network_id)
    
    if user_id:
        query = """
        SELECT g.* FROM groups g
        JOIN group_members gm ON g.group_id = gm.group_id
        WHERE gm.user_id = ?
        """
        query_params = [user_id]
        if network_id:
            query += " AND g.network_id = ?"
            query_params.append(network_id)
    
    query += " ORDER BY created_at DESC"
    
    cursor = db.execute(query, query_params)
    
    groups = []
    for row in cursor:
        group = dict(row)
        # Parse permissions JSON
        if group.get('permissions'):
            group['permissions'] = json.loads(group['permissions'])
        groups.append(group)
    
    return groups