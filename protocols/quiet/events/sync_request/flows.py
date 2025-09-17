"""
Flow for periodic sync requests.
"""
from __future__ import annotations

import uuid
import time
from typing import Dict, Any, List

from core.flows import FlowCtx, flow_op


@flow_op()  # Registers as 'sync_request.run'
def run(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Emit sync_request events from each identity to other users in their networks.

    Params:
    - since_ms (optional): last sync cutoff (default 0)

    Returns: { ids: {}, data: {sent: N} }
    """
    ctx = FlowCtx.from_params(params)
    since_ms = int(params.get('since_ms', 0))

    # Map identities to networks via users and peers
    # identities(identity_id) -> peers(peer_id, identity_id) -> users(peer_id, network_id)
    cursor = ctx.db.execute(
        """
        SELECT DISTINCT p.identity_id, u.network_id
        FROM users u
        JOIN peers p ON p.peer_id = u.peer_id
        WHERE u.network_id != ''
        """
    )
    pairs = cursor.fetchall()

    sent = 0
    for row in pairs:
        identity_id = row['identity_id'] if isinstance(row, dict) else row[0]
        network_id = row['network_id'] if isinstance(row, dict) else row[1]

        # Targets: other users in this network
        peers_cur = ctx.db.execute(
            """
            SELECT DISTINCT u.user_id
            FROM users u
            JOIN peers p ON p.peer_id = u.peer_id
            WHERE u.network_id = ? AND p.identity_id != ?
            """,
            (network_id, identity_id),
        )
        targets = [r['user_id'] if isinstance(r, dict) else r[0] for r in peers_cur.fetchall()]

        now_ms = int(time.time() * 1000)
        for target_user_id in targets:
            ctx.emit_event(
                'sync_request',
                {
                    'type': 'sync_request',
                    'request_id': str(uuid.uuid4()),
                    'network_id': network_id,
                    'from_identity': identity_id,
                    'to_peer': target_user_id,
                    'timestamp_ms': now_ms,
                    'last_sync_ms': since_ms,
                    'sync_all': True,
                },
                by=identity_id,
                deps=[],
                self_created=False,  # skip signing
                is_outgoing=True,    # sealed + not stored
                seal_to=target_user_id,
            )
            sent += 1

    return {'ids': {}, 'data': {'sent': sent}}

