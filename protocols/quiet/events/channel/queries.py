"""
Queries for channel event type.
"""
from core.db import ReadOnlyConnection
from typing import Dict, Any, List
import sqlite3
from core.queries import query


@query
def get(db: ReadOnlyConnection, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    List all channels.
    
    Optional params:
    - group_id: Filter by group
    - network_id: Filter by network
    """
    group_id = params.get('group_id')
    network_id = params.get('network_id')
    
    query = "SELECT * FROM channels WHERE 1=1"
    query_params = []
    
    if group_id:
        query += " AND group_id = ?"
        query_params.append(group_id)
    
    if network_id:
        query += " AND network_id = ?"
        query_params.append(network_id)
    
    query += " ORDER BY created_at DESC"
    
    cursor = db.execute(query, tuple(query_params))
    
    channels = []
    for row in cursor:
        channels.append(dict(row))
    
    return channels