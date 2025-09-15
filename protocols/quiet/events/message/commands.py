"""
Commands for message event type.
"""
import time
import sqlite3
from typing import Dict, Any, List
from core.core_types import command, response_handler


@command
def create_message(params: Dict[str, Any]) -> dict[str, Any]:
    """
    Create a new message in a channel.

    Returns an envelope with unsigned message event.
    """
    # Extract and validate required parameters
    content = params.get('content', '')
    if not content:
        raise ValueError("content is required")

    channel_id = params.get('channel_id', '')
    if not channel_id:
        raise ValueError("channel_id is required")

    identity_id = params.get('identity_id', '')
    if not identity_id:
        raise ValueError("identity_id is required")
    
    # Create message event (unsigned)
    event: Dict[str, Any] = {
        'type': 'message',
        'message_id': '',  # Will be filled by encrypt handler
        'channel_id': channel_id,
        'group_id': '',  # Will be filled by resolve_deps
        'network_id': '',  # Will be filled by resolve_deps
        'peer_id': identity_id,
        'content': content,
        'created_at': int(time.time() * 1000),
        'signature': ''  # Will be filled by sign handler
    }
    
    # Create envelope
    envelope: dict[str, Any] = {
        'event_plaintext': event,
        'event_type': 'message',
        'self_created': True,
        'peer_id': identity_id,
        'network_id': '',  # Will be filled by resolve_deps  
        'deps': [
            f"identity:{identity_id}",  # Need identity for signing
            f"channel:{channel_id}"  # Need channel for group_id/network_id
        ]
    }
    
    return envelope


@response_handler('create_message')
def create_message_response(stored_ids: Dict[str, str], params: Dict[str, Any], db: sqlite3.Connection) -> Dict[str, Any]:
    """
    Response handler for create_message command.
    Returns all recent messages in the channel including the newly created one.
    """
    channel_id = params.get('channel_id', '')

    # Get the newly created message ID
    new_message_id = stored_ids.get('message', '')

    # Query recent messages in the channel (last 50)
    cursor = db.execute("""
        SELECT m.message_id, m.content, m.channel_id, m.author_id, m.created_at, u.name as author_name
        FROM messages m
        LEFT JOIN users u ON m.author_id = u.user_id
        WHERE m.channel_id = ?
        ORDER BY m.created_at DESC
        LIMIT 50
    """, (channel_id,))

    messages = []
    for row in cursor:
        messages.append({
            'message_id': row[0],
            'content': row[1],
            'channel_id': row[2],
            'author_id': row[3],
            'created_at': row[4],
            'author_name': row[5] if row[5] else 'Unknown'
        })

    # Reverse to get chronological order (oldest first)
    messages.reverse()

    # Return response matching OpenAPI spec for create_message
    return {
        'message_id': new_message_id,
        'channel_id': channel_id,
        'content': params.get('content', ''),
        'messages': messages  # Recent messages in the channel
    }