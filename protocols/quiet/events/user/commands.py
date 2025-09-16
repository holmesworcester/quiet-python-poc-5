"""
Commands for user actions.
"""
import time
import json as json_module
import base64
import hashlib
from typing import Dict, Any
from core.crypto import generate_keypair, kdf, hash as crypto_hash
from core.core_types import command


@command
def join_as_user(params: Dict[str, Any]) -> list[dict[str, Any]]:
    """
    Join a network as a user using an invite link.

    Creates identity, peer, and user by calling their respective commands.
    Returns envelopes for all created events.
    """
    # Extract parameters
    invite_link = params.get('invite_link', '')
    name = params.get('name', '')
    db = params.get('_db')

    # Parse invite link
    if not invite_link.startswith("quiet://invite/"):
        raise ValueError("Invalid invite link format")

    invite_b64 = invite_link[15:]  # Remove prefix
    try:
        invite_json = base64.b64decode(invite_b64).decode()
        invite_data = json_module.loads(invite_json)
    except:
        raise ValueError("Invalid invite link encoding")

    invite_secret = invite_data.get('invite_secret')
    network_id = invite_data.get('network_id')
    group_id = invite_data.get('group_id')

    if not invite_secret or not network_id or not group_id:
        raise ValueError(f"Invalid invite data - missing required fields")

    # Generate name if not provided
    if not name:
        # Generate a simple default name
        import random
        name = f'User-{random.randint(1000, 9999)}'

    # Step 1: Create identity directly (can't use create_identity since it expects a path)
    from core.crypto import generate_keypair
    private_key, public_key = generate_keypair()

    # Calculate identity_id from public key
    identity_id = hashlib.blake2b(public_key, digest_size=16).hexdigest()

    # Store identity directly in core_identities table
    if db:
        db.execute("""
            INSERT INTO core_identities (
                identity_id, name, private_key, public_key, created_at
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            identity_id,
            name,
            private_key,
            public_key,
            int(time.time() * 1000)
        ))
        db.commit()
    else:
        raise ValueError("Database connection required for join_as_user")

    # Step 2: Create peer using peer command
    from protocols.quiet.events.peer.commands import create_peer
    peer_params = {
        'identity_id': identity_id,
        'username': name,
        'network_id': network_id,
        '_db': db
    }
    peer_envelope = create_peer(peer_params)

    # Step 3: Create user event with invite
    # Derive invite pubkey from secret
    invite_salt = hashlib.sha256(b"quiet_invite_kdf_v1").digest()[:16]
    derived_key = kdf(invite_secret.encode(), salt=invite_salt)
    invite_pubkey = derived_key.hex()

    # Create invite signature to prove we have the secret
    invite_sig_data = f"{invite_secret}:{public_key.hex()}:{network_id}"
    invite_signature = crypto_hash(invite_sig_data.encode()).hex()[:64]

    user_event: Dict[str, Any] = {
        'type': 'user',
        'peer_id': '@generated:peer:0',  # Placeholder for peer event's ID
        'network_id': network_id,
        'group_id': group_id,
        'name': name,
        'invite_pubkey': invite_pubkey,
        'invite_signature': invite_signature,
        'created_at': int(time.time() * 1000),
        'signature': ''  # Will be filled by sign handler
    }

    user_envelope = {
        'event_plaintext': user_event,
        'event_type': 'user',
        'self_created': True,
        'peer_id': '@generated:peer:0',  # Will be resolved to actual peer_id
        'network_id': network_id,
        'deps': [
            '@generated:peer:0',  # Depends on peer existing (placeholder)
            f"invite:{invite_pubkey}"  # Depends on invite existing
        ]
    }

    # Build the list of envelopes
    envelopes = []

    # 1. Identity event (local-only)
    identity_event: Dict[str, Any] = {
        'type': 'identity',
        'name': name,
        'network_id': network_id,
        'public_key': public_key.hex(),
        'created_at': int(time.time() * 1000)
    }

    envelopes.append({
        'event_plaintext': identity_event,
        'event_type': 'identity',
        'event_id': identity_id,
        'self_created': True,
        'validated': True,  # Identity events are local-only, immediately valid
        'write_to_store': True,
        'network_id': network_id,
        'deps': [],
        'deps_included_and_valid': True
    })

    # 2. Peer envelope (already created by create_peer)
    envelopes.append(peer_envelope)

    # 3. User envelope (already created above)
    envelopes.append(user_envelope)

    return envelopes



@command
def create_user(params: Dict[str, Any]) -> dict[str, Any]:
    """
    Create a basic user event.

    For invite-based joining, use join_as_user instead.

    Returns an envelope with unsigned user event.
    """
    # Extract parameters - frontend provides peer_id
    peer_id = params.get('peer_id', '')
    network_id = params.get('network_id', '')
    name = params.get('name', 'User')
    group_id = params.get('group_id', '')  # Optional - which group to join

    if not peer_id:
        raise ValueError("peer_id is required")
    if not network_id:
        raise ValueError("network_id is required")

    # Create user event (unsigned)
    event: Dict[str, Any] = {
        'type': 'user',
        'user_id': '',  # Will be filled by crypto handler
        'peer_id': peer_id,  # The peer creating this user
        'network_id': network_id,
        'group_id': group_id,  # Optional group to join
        'name': name,
        'created_at': int(time.time() * 1000),
        'signature': ''  # Will be filled by sign handler
    }

    # Create envelope
    envelope: dict[str, Any] = {
        'event_plaintext': event,
        'event_type': 'user',
        'self_created': True,
        'peer_id': peer_id,  # Peer that will sign this
        'network_id': network_id,
        'deps': [f'peer:{peer_id}']  # Depends on peer existing
    }

    return envelope