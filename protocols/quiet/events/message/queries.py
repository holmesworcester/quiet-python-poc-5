"""
Queries for message event type.
"""
from typing import Dict, Any, List
import sqlite3


def list_messages(params: Dict[str, Any], db: sqlite3.Connection) -> List[Dict[str, Any]]:
    """
    List messages.
    
    Optional params:
    - channel_id: Filter by channel (recommended)
    - group_id: Filter by group
    - limit: Maximum number of messages (default 100)
    - offset: Offset for pagination
    """
    channel_id = params.get('channel_id')
    group_id = params.get('group_id')
    limit = params.get('limit', 100)
    offset = params.get('offset', 0)
    
    query = "SELECT * FROM messages WHERE 1=1"
    query_params = []
    
    if channel_id:
        query += " AND channel_id = ?"
        query_params.append(channel_id)
    
    if group_id:
        query += " AND group_id = ?"
        query_params.append(group_id)
    
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    query_params.extend([limit, offset])
    
    cursor = db.execute(query, query_params)
    
    messages = []
    for row in cursor:
        messages.append(dict(row))
    
    # Return in chronological order for display
    messages.reverse()
    
    return messages