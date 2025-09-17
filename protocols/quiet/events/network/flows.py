"""
Flows for network operations.
"""
from __future__ import annotations

from typing import Dict, Any
import time

from core.flows import FlowCtx, flow_op


@flow_op()  # Registers as 'network.create'
def create(params: Dict[str, Any]) -> Dict[str, Any]:
    ctx = FlowCtx.from_params(params)

    name = params.get('name', '')
    peer_id = params.get('peer_id') or params.get('identity_id')
    if not name:
        raise ValueError('name is required')
    if not peer_id:
        raise ValueError('peer_id is required - create a peer first')

    network_id = ctx.emit_event(
        'network',
        {
            'name': name,
            'creator_id': peer_id,
            'created_at': int(time.time() * 1000),
        },
        by=peer_id,
        deps=[f'peer:{peer_id}'],
    )
    return {'ids': {'network': network_id}, 'data': {}}
