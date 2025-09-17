"""
Flows for channel operations.
"""
from __future__ import annotations

from typing import Any, Dict, List

from core.flows import FlowCtx, flow_op
import time


@flow_op()  # Registers as 'channel.create'
def create(params: Dict[str, Any]) -> Dict[str, Any]:
    ctx = FlowCtx.from_params(params)
    group_id = params.get('group_id', '')

    peer_id = params.get('peer_id', '')
    name = params.get('name', '')
    network_id = params.get('network_id', '')
    if not peer_id:
        raise ValueError('peer_id is required for create_channel')
    if not group_id:
        raise ValueError('group_id is required for create_channel')

    new_channel_id = ctx.emit_event(
        'channel',
        {
            'group_id': group_id,
            'name': name,
            'network_id': network_id,
            'creator_id': peer_id,
            'created_at': int(time.time() * 1000),
        },
        by=peer_id,
        deps=[f'group:{group_id}'],
    )

    cursor = ctx.db.execute(
        """
        SELECT channel_id, name, group_id, created_at
        FROM channels
        WHERE group_id = ?
        ORDER BY created_at DESC
        """,
        (group_id,),
    )

    channels: List[Dict[str, Any]] = []
    for row in cursor:
        channels.append({
            'channel_id': row[0],
            'name': row[1],
            'group_id': row[2],
            'created_at': row[3],
        })

    return {
        'ids': {'channel': new_channel_id},
        'data': {
            'channel_id': new_channel_id,
            'name': params.get('name', ''),
            'group_id': group_id,
            'channels': channels,
        },
    }
