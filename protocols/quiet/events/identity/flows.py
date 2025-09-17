"""
Flows for identity operations.
"""
from __future__ import annotations

import time
import hashlib
from typing import Dict, Any

from core.flows import FlowCtx, flow_op
from core import crypto


@flow_op()  # Registers as 'identity.create'
def create(params: Dict[str, Any]) -> Dict[str, Any]:
    """Create a local-only identity (keypair) and return its id."""
    ctx = FlowCtx.from_params(params)
    name = params.get('name', 'User')
    priv, pub = crypto.generate_keypair()
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

    return {
        'ids': {'identity': identity_id},
        'data': {
            'identity_id': identity_id,
            'name': name,
            'public_key': pub.hex(),
        },
    }

@flow_op()  # Registers as 'identity.create_as_user'
def create_as_user(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a local identity and bootstrap initial network state:
    identity -> peer -> network -> group -> user -> channel (optional).

    Params:
    - name: identity/user display name (required)
    - network_name: optional, default 'My Network'
    - group_name: optional, default 'General'
    - channel_name: optional, default 'general'

    Returns: { ids: {identity, peer, network, group, user, channel?}, data: {...} }
    """
    ctx = FlowCtx.from_params(params)

    name = params.get('name', '').strip()
    if not name:
        raise ValueError('name is required')
    network_name = params.get('network_name', 'My Network')
    group_name = params.get('group_name', 'General')
    channel_name = params.get('channel_name', 'general')

    # 1) Identity (local-only)
    priv, pub = crypto.generate_keypair()
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

    # 2) Peer (self-attested)
    peer_id = ctx.emit_event(
        'peer',
        {
            'public_key': pub.hex(),
            'identity_id': identity_id,
            'username': name,
            'created_at': int(time.time() * 1000),
        },
        by=identity_id,
        deps=[],
    )

    # 3) Network
    network_id = ctx.emit_event(
        'network',
        {
            'name': network_name,
            'creator_id': peer_id,
            'created_at': int(time.time() * 1000),
        },
        by=peer_id,
        deps=[f'peer:{peer_id}'],
    )

    # 4) Group (creator automatically added as member by projector)
    group_id = ctx.emit_event(
        'group',
        {
            'name': group_name,
            'network_id': network_id,
            'creator_id': peer_id,
            'created_at': int(time.time() * 1000),
        },
        by=peer_id,
        deps=[],
    )

    # 5) User for this identity/peer in the network/group
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

    # 6) Default channel in the group
    channel_id = ctx.emit_event(
        'channel',
        {
            'group_id': group_id,
            'name': channel_name,
            'network_id': network_id,
            'creator_id': peer_id,
            'created_at': int(time.time() * 1000),
        },
        by=peer_id,
        deps=[f'group:{group_id}'],
    )

    return {
        'ids': {
            'identity': identity_id,
            'peer': peer_id,
            'network': network_id,
            'group': group_id,
            'user': user_id,
            'channel': channel_id,
        },
        'data': {
            'name': name,
            'network_name': network_name,
            'group_name': group_name,
            'channel_name': channel_name,
        },
    }
