"""
Commands for user actions.
"""
import time
import json as json_module
import base64
import hashlib
from typing import Dict, Any
from core.crypto import generate_keypair, kdf, hash as crypto_hash
from core.core_types import command, response_handler
import sqlite3


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

    # Step 2: Create peer event
    peer_event: Dict[str, Any] = {
        'type': 'peer',
        'peer_id': '',  # Will be filled by crypto handler
        'public_key': public_key.hex(),
        'identity_id': identity_id,
        'network_id': network_id,
        'username': name,
        'created_at': int(time.time() * 1000),
        'signature': ''  # Will be filled by sign handler
    }

    peer_envelope = {
        'event_plaintext': peer_event,
        'event_type': 'peer',
        'self_created': True,
        'network_id': network_id,
        'deps': []
    }

    # Step 3: Create user event with invite
    # Derive invite pubkey from secret
    invite_salt = hashlib.sha256(b"quiet_invite_kdf_v1").digest()[:16]
    derived_key = kdf(invite_secret.encode(), salt=invite_salt)
    invite_pubkey = derived_key.hex()

    # Create invite signature to prove we have the secret
    invite_sig_data = f"{invite_secret}:{public_key.hex()}:{network_id}"
    invite_signature = crypto_hash(invite_sig_data.encode()).hex()[:64]

    # For user event, use placeholder reference to peer that will be created
    user_event: Dict[str, Any] = {
        'type': 'user',
        'peer_id': '@generated:peer:0',  # Reference to first peer event in this command
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
        'peer_id': '@generated:peer:0',  # Reference to peer that will sign this
        'network_id': network_id,
        'deps': [
            '@generated:peer:0',  # Depends on peer being created first
            f"invite:{invite_pubkey}"  # Depends on invite existing
        ]
    }

    # Build the list of envelopes in order
    envelopes = []

    # 1. Peer envelope first (creates the peer)
    envelopes.append(peer_envelope)

    # 2. User envelope (depends on peer existing, but we can't reference it yet)
    # The API will need to handle this by processing peer first, then using its ID
    envelopes.append(user_envelope)

    return envelopes



@response_handler('join_as_user')
def join_as_user_response(stored_ids: Dict[str, str], params: Dict[str, Any], db: sqlite3.Connection) -> Dict[str, Any]:
    """
    Response handler for join_as_user command.
    Returns the identity ID along with peer and user IDs.
    """
    # The identity was created directly in the DB by join_as_user
    # We need to extract it from the params since it's not an event

    # Parse invite link to get the identity that was created
    invite_link = params.get('invite_link', '')
    name = params.get('name', '')

    # Query for the identity that was just created with this name
    cursor = db.execute("""
        SELECT identity_id FROM core_identities
        WHERE name = ?
        ORDER BY created_at DESC
        LIMIT 1
    """, (name,))

    row = cursor.fetchone()
    identity_id = row['identity_id'] if row else None

    # Add identity to the stored_ids
    if identity_id:
        stored_ids['identity'] = identity_id

    return {
        'ids': stored_ids,
        'data': {
            'name': name,
            'joined': True
        }
    }


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