"""
Flows for user-related multi-step operations.

Flows are read-only orchestrations that can query, emit, and return.
They do not write to the DB directly; all state changes happen via emitted events.
"""
from __future__ import annotations

import base64
import hashlib
import json as json_module
from typing import Any, Dict

from core.crypto import kdf, hash as crypto_hash, generate_keypair
from core.flows import FlowCtx, flow_op
import time


@flow_op()  # Registers as 'user.join_as_user'
def join_as_user(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flow: create identity (local-only), then peer, then user via invite.

    Expects the following execution context in params:
      - _db: sqlite3.Connection
      - _runner: PipelineRunner
      - _protocol_dir: str
      - _request_id: str

    Returns ids and minimal data; the command wrapper may still use a response handler.
    """
    invite_link = params.get('invite_link', '')
    name = params.get('name', '')

    ctx = FlowCtx.from_params(params)

    if not invite_link.startswith("quiet://invite/"):
        raise ValueError("Invalid invite link format")

    invite_b64 = invite_link[15:]
    try:
        invite_json = base64.b64decode(invite_b64).decode()
        invite_data = json_module.loads(invite_json)
    except Exception:
        raise ValueError("Invalid invite link encoding")

    invite_secret = invite_data.get('invite_secret')
    network_id = invite_data.get('network_id')
    group_id = invite_data.get('group_id')
    if not invite_secret or not network_id or not group_id:
        raise ValueError("Invalid invite data - missing required fields")

    if not name:
        raise ValueError("name is required for join_as_user")

    # ctx validates presence of db, runner, protocol_dir

    # 1) Identity (local-only)
    priv, pub = generate_keypair()
    identity_id = hashlib.blake2b(pub, digest_size=16).hexdigest()
    ctx.emit_event(
        'identity',
        {
            'identity_id': identity_id,
            'name': name,
            'public_key': pub.hex(),
            'private_key': priv.hex(),
            'created_at': int(time.time() * 1000),
        },
        local_only=True,
        deps=[],
    )
    public_key_hex = pub.hex()

    # 2) Peer
    peer_id = ctx.emit_event(
        'peer',
        {
            'public_key': public_key_hex,
            'identity_id': identity_id,
            'username': name,
            'created_at': int(time.time() * 1000),
        },
        by=identity_id,
        deps=[],
    )
    if not peer_id:
        raise ValueError(f"Failed to create peer for identity {identity_id}")

    # 3) User
    invite_salt = hashlib.sha256(b"quiet_invite_kdf_v1").digest()[:16]
    derived_key = kdf(invite_secret.encode(), salt=invite_salt)
    invite_pubkey = derived_key.hex()
    invite_sig_data = f"{invite_secret}:{public_key_hex}:{network_id}"
    invite_signature = crypto_hash(invite_sig_data.encode()).hex()[:64]

    user_id = ctx.emit_event(
        'user',
        {
            'peer_id': peer_id,
            'network_id': network_id,
            'group_id': group_id,
            'name': name,
            'invite_pubkey': invite_pubkey,
            'invite_signature': invite_signature,
            'created_at': int(time.time() * 1000),
        },
        by=peer_id,
        deps=[f'peer:{peer_id}'],
    )
    if not user_id:
        raise ValueError("Failed to create user after peer creation")

    return {
        'ids': {
            'identity': identity_id,
            'peer': peer_id,
            'user': user_id,
        },
        'data': {
            'name': name,
            'joined': True,
        }
    }


@flow_op()  # Registers as 'user.create'
def create(params: Dict[str, Any]) -> Dict[str, Any]:
    """Create a basic user event (without invite)."""
    ctx = FlowCtx.from_params(params)
    peer_id = params.get('peer_id', '')
    network_id = params.get('network_id', '')
    name = params.get('name', 'User')
    group_id = params.get('group_id', '')
    if not peer_id or not network_id:
        raise ValueError('peer_id and network_id are required')

    user_id = ctx.emit_event(
        'user',
        {
            'peer_id': peer_id,
            'network_id': network_id,
            'group_id': group_id,
            'name': name,
            'created_at': int(time.time() * 1000),
        },
        by=peer_id,
        deps=[f'peer:{peer_id}'],
    )

    return {'ids': {'user': user_id}, 'data': {'user_id': user_id}}
