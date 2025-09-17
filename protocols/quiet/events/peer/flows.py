"""
Flows for peer operations.
"""
from __future__ import annotations

from typing import Dict

from core.flows import FlowCtx, flow_op
import time


@flow_op()  # Registers as 'peer.create'
def create(params: Dict[str, any]) -> Dict[str, any]:
    ctx = FlowCtx.from_params(params)

    identity_id = params.get('identity_id', '')
    username = params.get('username', 'User')
    if not identity_id:
        raise ValueError('identity_id is required')

    # Fetch public key for identity
    row = ctx.db.execute(
        "SELECT public_key FROM identities WHERE identity_id = ?",
        (identity_id,),
    ).fetchone()
    if not row:
        raise ValueError(f'Identity {identity_id} not found')
    public_key_hex = row['public_key'] if isinstance(row['public_key'], str) else row['public_key'].hex()

    peer_id = ctx.emit_event(
        'peer',
        {
            'public_key': public_key_hex,
            'identity_id': identity_id,
            'username': username,
            'created_at': int(time.time() * 1000),
        },
        by=identity_id,
        deps=[],
    )
    return {'ids': {'peer': peer_id}, 'data': {}}
