"""
Queries for message event type.
"""
from core.db import ReadOnlyConnection
from typing import Dict, Any, List
import sqlite3
from core.queries import query


@query
def get(db: ReadOnlyConnection, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    List messages visible to an identity.

    Required params:
    - identity_id: Identity requesting the messages

    Optional params:
    - channel_id: Filter by channel (recommended)
    - group_id: Filter by group
    - limit: Maximum number of messages (default 100)
    - offset: Offset for pagination
    """
    # identity_id is required for access control
    identity_id = params.get('identity_id')
    if not identity_id:
        raise ValueError("identity_id is required for get_messages")

    channel_id = params.get('channel_id')
    group_id = params.get('group_id')
    limit = params.get('limit', 100)
    offset = params.get('offset', 0)
    
    # Check that identity exists
    # TODO: Add proper group membership check using members table
    # Should verify: identity -> user -> member -> group -> channel
    # For now, just verify the identity exists and allow access if channel_id is provided
    query = """
        SELECT m.*
        FROM messages m
        WHERE EXISTS (
            SELECT 1 FROM identities i
            WHERE i.identity_id = ?
        )
    """
    query_params = [identity_id]

    if channel_id:
        query += " AND m.channel_id = ?"
        query_params.append(channel_id)

    if group_id:
        query += " AND m.group_id = ?"
        query_params.append(group_id)
    
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    query_params.extend([limit, offset])
    
    cursor = db.execute(query, tuple(query_params))
    
    messages = []
    for row in cursor:
        messages.append(dict(row))
    
    # Return in chronological order for display
    messages.reverse()
    
    return messages