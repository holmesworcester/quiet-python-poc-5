"""
Flows for message operations.
"""
from __future__ import annotations

from typing import Any, Dict, List

from core.flows import FlowCtx, flow_op
import time


@flow_op()  # Registers as 'message.create'
def create(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Emit message.create_message and return recent messages in the channel.
    """
    ctx = FlowCtx.from_params(params)
    channel_id = params.get('channel_id', '')

    peer_id = params.get('peer_id', '')
    if not peer_id:
        raise ValueError('peer_id is required for create_message')

    new_message_id = ctx.emit_event(
        'message',
        {
            'channel_id': channel_id,
            'group_id': '',  # resolve_deps fills
            'network_id': '',  # resolve_deps fills
            'peer_id': peer_id,
            'content': params.get('content', ''),
            'created_at': int(time.time() * 1000),
        },
        by=peer_id,
        deps=[f'channel:{channel_id}', f'peer:{peer_id}'],
    )

    cursor = ctx.db.execute(
        """
        SELECT m.message_id, m.content, m.channel_id, m.author_id, m.created_at, u.name as author_name
        FROM messages m
        LEFT JOIN users u ON m.author_id = u.user_id
        WHERE m.channel_id = ?
        ORDER BY m.created_at DESC
        LIMIT 50
        """,
        (channel_id,),
    )

    messages: List[Dict[str, Any]] = []
    for row in cursor:
        messages.append({
            'message_id': row[0],
            'content': row[1],
            'channel_id': row[2],
            'author_id': row[3],
            'created_at': row[4],
            'author_name': row[5] if row[5] else 'Unknown'
        })
    messages.reverse()

    return {
        'ids': {'message': new_message_id},
        'data': {
            'message_id': new_message_id,
            'channel_id': channel_id,
            'content': params.get('content', ''),
            'messages': messages,
        },
    }
