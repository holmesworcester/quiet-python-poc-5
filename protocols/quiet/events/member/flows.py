"""
Flows for member operations.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List

from core.flows import FlowCtx, flow_op


@flow_op()  # Registers as 'member.create'
def create(params: Dict[str, Any]) -> Dict[str, Any]:
    ctx = FlowCtx.from_params(params)
    group_id = params.get('group_id', '')
    user_id = params.get('user_id', '')
    peer_id = params.get('peer_id') or params.get('identity_id', '')
    network_id = params.get('network_id', '')

    if not group_id or not user_id or not peer_id or not network_id:
        raise ValueError('group_id, user_id, peer_id, network_id are required')

    add_id = ctx.emit_event(
        'member',
        {
            'group_id': group_id,
            'user_id': user_id,
            'added_by': peer_id,
            'network_id': network_id,
            'created_at': int(time.time() * 1000),
        },
        by=peer_id,
        deps=[f'group:{group_id}', f'user:{user_id}'],
    )

    cursor = ctx.db.execute(
        """
        SELECT u.user_id, u.name, u.peer_id, u.created_at
        FROM users u
        JOIN group_members gm ON u.user_id = gm.user_id
        WHERE gm.group_id = ?
        ORDER BY u.created_at DESC
        """,
        (group_id,),
    )

    members: List[Dict[str, Any]] = []
    for row in cursor:
        members.append({
            'user_id': row[0],
            'name': row[1],
            'peer_id': row[2],
            'created_at': row[3],
        })

    return {
        'ids': {'member': add_id},
        'data': {
            'group_id': group_id,
            'members': members,
            'member_count': len(members),
        },
    }
