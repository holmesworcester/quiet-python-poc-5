"""
Flows for address announcements.
"""
from __future__ import annotations

import time
from typing import Dict, Any

from core.flows import FlowCtx, flow_op


@flow_op()  # Registers as 'address.announce'
def announce(params: Dict[str, Any]) -> Dict[str, Any]:
    ctx = FlowCtx.from_params(params)

    peer_id = params.get('peer_id', '')
    ip = params.get('ip', '127.0.0.1')
    port = int(params.get('port', 5000))
    action = params.get('action', 'add')
    network_id = params.get('network_id', '')

    if not peer_id:
        raise ValueError('peer_id is required for announce_address')

    addr_id = ctx.emit_event(
        'address',
        {
            'action': action,
            'peer_id': peer_id,
            'ip': ip,
            'port': port,
            'network_id': network_id,
            'timestamp_ms': int(time.time() * 1000),
        },
        by=peer_id,
        deps=[f'peer:{peer_id}'],
    )

    return {'ids': {'address': addr_id}, 'data': {}}
