"""
Flows for invite operations.
"""
from __future__ import annotations

import base64
import json
import time
import secrets
import hashlib
from typing import Any, Dict

from core.crypto import kdf
from core.flows import FlowCtx, flow_op


@flow_op()  # Registers as 'invite.create'
def create(params: Dict[str, Any]) -> Dict[str, Any]:
    ctx = FlowCtx.from_params(params)

    network_id = params.get('network_id', '')
    group_id = params.get('group_id', '')
    peer_id = params.get('peer_id', '')
    if not peer_id:
        raise ValueError('peer_id is required for create_invite')

    # Generate invite secret and derive pubkey
    invite_secret = secrets.token_urlsafe(32)
    invite_salt = hashlib.sha256(b"quiet_invite_kdf_v1").digest()[:16]
    derived_key = kdf(invite_secret.encode(), salt=invite_salt)
    invite_pubkey = derived_key.hex()

    invite_id = ctx.emit_event(
        'invite',
        {
            'invite_pubkey': invite_pubkey,
            'invite_secret': invite_secret,
            'network_id': network_id,
            'group_id': group_id,
            'inviter_id': peer_id,
            'created_at': int(time.time() * 1000),
        },
        by=peer_id,
        deps=[f'group:{group_id}'],
    )

    invite_data = {
        'invite_secret': invite_secret,
        'network_id': network_id,
        'group_id': group_id,
    }
    invite_json = json.dumps(invite_data)
    invite_code = base64.b64encode(invite_json.encode()).decode()
    invite_link = f"quiet://invite/{invite_code}"

    return {
        'ids': {'invite': invite_id},
        'data': {
            'invite_link': invite_link,
            'invite_code': invite_code,
            'invite_id': invite_id,
            'network_id': network_id,
            'group_id': group_id,
        },
    }
