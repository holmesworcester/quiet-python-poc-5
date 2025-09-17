"""
Scenario: Out-of-order delivery with sync and scheduler tick.

We simulate two peers (Alice and Bob) using two separate databases. Alice
creates a network, channel, and a message. We then hand-craft incoming
envelopes for Bob to simulate out-of-order delivery: the message arrives
before the channel. The pipeline should block the message, and once the
channel arrives, unblocking should project the message.

We also invoke the scheduler tick to ensure it runs alongside this flow.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Dict, Any
import hashlib
import json

from core.api import APIClient
from core.db import get_connection
from core.crypto import sign
from protocols.quiet.handlers.signature import canonicalize_event


def blake2_16_hex(data: bytes) -> str:
    return hashlib.blake2b(data, digest_size=16).hexdigest()


def enc_ciphertext_for_plaintext(pt: Dict[str, Any]) -> bytes:
    # Matches stub in protocols/quiet/handlers/crypto.encrypt_event
    return f"encrypted:{str(pt)}".encode()


def sign_plaintext(pt: Dict[str, Any], priv_hex: str | bytes) -> str:
    # Compute canonical form and sign with Ed25519 (matches signature handler)
    canonical = canonicalize_event(pt)
    if isinstance(priv_hex, (bytes, bytearray)):
        priv_bytes = bytes(priv_hex)
    else:
        priv_bytes = bytes.fromhex(priv_hex)
    return sign(canonical, priv_bytes).hex()


def build_env(event_type: str, pt_fields_in_order: list[tuple[str, Any]], priv_hex: str | bytes, *,
              preset_sig: bool = True, preset_cipher_id: bool = True,
              preset_validated: bool = True, preset_deps_valid: bool = True) -> Dict[str, Any]:
    # Build plaintext in the exact insertion order used by flows
    pt: Dict[str, Any] = {'type': event_type}
    for k, v in pt_fields_in_order:
        pt[k] = v
    if preset_sig:
        pt['signature'] = sign_plaintext(pt.copy(), priv_hex)

    env: Dict[str, Any] = {
        'event_type': event_type,
        'event_plaintext': pt,
        'self_created': False,
        'is_outgoing': False,
    }

    if preset_cipher_id:
        ct = enc_ciphertext_for_plaintext(pt)
        env['event_ciphertext'] = ct
        env['event_id'] = blake2_16_hex(ct)

    if preset_validated:
        env['sig_checked'] = True
        env['validated'] = True

    if preset_deps_valid:
        env['deps_included_and_valid'] = True

    return env


def test_out_of_order_delivery_with_tick():
    # Create two separate databases for Alice and Bob
    with tempfile.NamedTemporaryFile(suffix='.db') as alice_tmp, tempfile.NamedTemporaryFile(suffix='.db') as bob_tmp:
        alice_api = APIClient(protocol_dir=Path('protocols/quiet'), reset_db=True, db_path=Path(alice_tmp.name))
        bob_api = APIClient(protocol_dir=Path('protocols/quiet'), reset_db=True, db_path=Path(bob_tmp.name))

        # Bootstrap Alice: identity → peer → network → group → channel
        boot = alice_api.execute_operation('identity.create_as_user', {
            'name': 'Alice',
            'network_name': 'Net A',
            'group_name': 'Main',
            'channel_name': 'general',
        })
        alice_ids = boot['ids']
        alice_identity = alice_ids['identity']
        alice_peer = alice_ids['peer']
        alice_network = alice_ids['network']
        alice_group = alice_ids['group']
        alice_channel = alice_ids['channel']

        # Alice sends a message in her channel
        msg_res = alice_api.execute_operation('message.create', {
            'peer_id': alice_peer,
            'channel_id': alice_channel,
            'content': 'Hello from Alice!'
        })
        alice_message = msg_res['ids']['message']

        # Pull raw state needed to reconstruct plaintext and signatures
        alice_db = get_connection(str(alice_tmp.name))
        try:
            # Identity private key (hex)
            row = alice_db.execute(
                "SELECT private_key FROM identities WHERE identity_id = ?",
                (alice_identity,)
            ).fetchone()
            assert row is not None, 'Alice identity not stored'
            alice_priv = row['private_key'] if isinstance(row['private_key'], str) else row['private_key'].hex()

            # Timestamps and names from projections
            peer_row = alice_db.execute(
                "SELECT created_at FROM peers WHERE peer_id = ?",
                (alice_peer,)
            ).fetchone()
            net_row = alice_db.execute(
                "SELECT name, created_at, creator_id FROM networks WHERE network_id = ?",
                (alice_network,)
            ).fetchone()
            grp_row = alice_db.execute(
                "SELECT name, created_at, network_id, creator_id FROM groups WHERE group_id = ?",
                (alice_group,)
            ).fetchone()
            ch_row = alice_db.execute(
                "SELECT name, created_at, group_id, network_id, creator_id FROM channels WHERE channel_id = ?",
                (alice_channel,)
            ).fetchone()
            msg_row = alice_db.execute(
                "SELECT content, created_at, author_id, channel_id, group_id, network_id FROM messages WHERE message_id = ?",
                (alice_message,)
            ).fetchone()

            assert peer_row and net_row and grp_row and ch_row and msg_row, 'Missing projection rows in Alice DB'

            peer_created_at = peer_row['created_at']
            net_name, net_created_at, net_creator = net_row['name'], net_row['created_at'], net_row['creator_id']
            grp_name, grp_created_at, grp_net, grp_creator = grp_row['name'], grp_row['created_at'], grp_row['network_id'], grp_row['creator_id']
            ch_name, ch_created_at, ch_group, ch_net, ch_creator = ch_row['name'], ch_row['created_at'], ch_row['group_id'], ch_row['network_id'], ch_row['creator_id']
            msg_content, msg_created_at, msg_author, msg_channel, msg_group, msg_net = (
                msg_row['content'], msg_row['created_at'], msg_row['author_id'], msg_row['channel_id'], msg_row['group_id'], msg_row['network_id']
            )
        finally:
            alice_db.close()

        # Construct inbound envelopes for Bob
        # 1) Peer (so Bob can resolve the author public key)
        peer_pt_fields = [
            ('public_key', None),  # fill below
            ('identity_id', alice_identity),
            ('username', 'Alice'),
            ('created_at', peer_created_at),
        ]
        # Get Alice public key from identities table
        alice_db2 = get_connection(str(alice_tmp.name))
        try:
            pub_row = alice_db2.execute(
                "SELECT public_key FROM identities WHERE identity_id = ?",
                (alice_identity,)
            ).fetchone()
            assert pub_row is not None
            alice_pub = pub_row['public_key'] if isinstance(pub_row['public_key'], str) else pub_row['public_key'].hex()
        finally:
            alice_db2.close()
        peer_pt_fields[0] = ('public_key', alice_pub)
        peer_env = build_env('peer', peer_pt_fields, alice_priv)

        # 2) Message (arrives first, before channel) - do NOT preset validation/deps
        msg_pt_fields = [
            ('channel_id', msg_channel),
            ('group_id', msg_group),
            ('network_id', msg_net),
            ('peer_id', msg_author),
            ('content', msg_content),
            ('created_at', msg_created_at),
        ]
        msg_env = build_env('message', msg_pt_fields, alice_priv,
                            preset_sig=True, preset_cipher_id=True,
                            preset_validated=False, preset_deps_valid=False)

        # 3) Channel (arrives later, triggers unblocking)
        # Order must match flows: group_id, name, network_id, creator_id, created_at
        ch_pt_fields = [
            ('group_id', ch_group),
            ('name', ch_name),
            ('network_id', ch_net),
            ('creator_id', ch_creator),
            ('created_at', ch_created_at),
        ]
        ch_env = build_env('channel', ch_pt_fields, alice_priv)

        # Inject into Bob in out-of-order sequence: peer -> message -> tick -> channel
        # Use runner directly with Bob's DB connection
        bob_db = get_connection(str(bob_tmp.name))
        try:
            # Peer first
            bob_api.runner.run(protocol_dir=str(bob_api.protocol_dir), input_envelopes=[peer_env], db=bob_db)

            # Message before channel: should be blocked (no projection yet)
            bob_api.runner.run(protocol_dir=str(bob_api.protocol_dir), input_envelopes=[msg_env], db=bob_db)

            # Ensure message not projected yet
            row = bob_db.execute(
                "SELECT COUNT(*) AS c FROM messages WHERE message_id = ?",
                (alice_message,)
            ).fetchone()
            assert row['c'] == 0, 'Message should not be projected before channel arrives'

            # Tick scheduler (runs sync_request job; not required for unblocking but part of scenario)
            jobs_triggered = bob_api.tick_scheduler()
            assert jobs_triggered >= 0

            # Now deliver channel, which should unblock the message
            bob_api.runner.run(protocol_dir=str(bob_api.protocol_dir), input_envelopes=[ch_env], db=bob_db)

            # After channel processing, the blocked message should be unblocked and projected
            row2 = bob_db.execute(
                "SELECT content FROM messages WHERE message_id = ?",
                (alice_message,)
            ).fetchone()
            assert row2 is not None, 'Message should be projected after channel arrives'
            assert row2['content'] == msg_content

        finally:
            bob_db.close()
