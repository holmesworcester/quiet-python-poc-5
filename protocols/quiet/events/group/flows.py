"""
Flows for group operations.
"""
from __future__ import annotations

from typing import Any, Dict, List

from core.flows import FlowCtx, flow_op
import time


@flow_op()  # Registers as 'group.create'
def create(params: Dict[str, Any]) -> Dict[str, Any]:
    ctx = FlowCtx.from_params(params)
    network_id = params.get('network_id', '')

    peer_id = params.get('peer_id', '')
    name = params.get('name', '')
    if not peer_id:
        raise ValueError('peer_id is required for create_group')
    if not network_id:
        raise ValueError('network_id is required for create_group')

    new_group_id = ctx.emit_event(
        'group',
        {
            'name': name,
            'network_id': network_id,
            'creator_id': peer_id,
            'created_at': int(time.time() * 1000),
        },
        by=peer_id,
        deps=[],
    )

    cursor = ctx.db.execute(
        """
        SELECT group_id, name, creator_id, created_at
        FROM groups
        WHERE network_id = ?
        ORDER BY created_at DESC
        """,
        (network_id,),
    )

    groups: List[Dict[str, Any]] = []
    for row in cursor:
        groups.append({
            'group_id': row[0],
            'name': row[1],
            'creator_id': row[2],
            'created_at': row[3],
        })

    return {
        'ids': {'group': new_group_id},
        'data': {
            'group_id': new_group_id,
            'name': params.get('name', ''),
            'network_id': network_id,
            'creator_id': peer_id,
            'groups': groups,
        },
    }
