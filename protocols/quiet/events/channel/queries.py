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
    List channels visible to an identity.

    Required params:
    - identity_id: Identity requesting the channels

    Optional params:
    - group_id: Filter by group
    - network_id: Filter by network
    """
    # identity_id is required for access control
    identity_id = params.get('identity_id')
    if not identity_id:
        raise ValueError("identity_id is required for get_channels")

    group_id = params.get('group_id')
    network_id = params.get('network_id')

    # Only show channels the identity has access to
    # TODO: Check group membership properly
    query = """
        SELECT * FROM channels
        WHERE EXISTS (
            SELECT 1 FROM identities i
            WHERE i.identity_id = ?
        )
    """
    query_params = [identity_id]
    
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