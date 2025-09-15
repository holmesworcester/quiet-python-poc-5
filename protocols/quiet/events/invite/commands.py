"""
Commands for invite event type.
"""
import time
import hashlib
import secrets
import json
import base64
from typing import Dict, Any
from core.crypto import kdf
from core.core_types import command, response_handler
from core.db import ReadOnlyConnection


@command
def create_invite(params: Dict[str, Any]) -> dict[str, Any]:
    """
    Create a new invite to join a network.

    Returns an envelope with unsigned invite event and invite link data.
    """
    # Extract parameters
    network_id = params.get('network_id', '')
    group_id = params.get('group_id', '')  # First group to join
    identity_id = params.get('identity_id', '')

    # Generate invite secret
    invite_secret = secrets.token_urlsafe(32)

    # Derive invite pubkey from secret using KDF (like POC-3)
    # Use deterministic salt for invites so both parties derive same key
    invite_salt = hashlib.sha256(b"quiet_invite_kdf_v1").digest()[:16]
    derived_key = kdf(invite_secret.encode(), salt=invite_salt)
    invite_pubkey = derived_key.hex()

    # Create invite event (unsigned)
    # The invite_id will be the event_id (hash of the signed event)
    event: Dict[str, Any] = {
        'type': 'invite',
        'invite_pubkey': invite_pubkey,
        'invite_secret': invite_secret,  # Store secret so response handler can recreate link
        'network_id': network_id,
        'group_id': group_id,
        'inviter_id': identity_id,
        'created_at': int(time.time() * 1000),
        'signature': ''  # Will be filled by sign handler
    }

    # Create invite link data
    invite_data = {
        'invite_secret': invite_secret,
        'network_id': network_id,
        'group_id': group_id
    }

    # Encode invite link
    invite_json = json.dumps(invite_data)
    invite_b64 = base64.b64encode(invite_json.encode()).decode()
    invite_link = f"quiet://invite/{invite_b64}"

    # Create envelope
    envelope: dict[str, Any] = {
        'event_plaintext': event,
        'event_type': 'invite',
        'self_created': True,
        'peer_id': identity_id,
        'network_id': network_id,
        'deps': [f"group:{group_id}"],  # Invite depends on group existing
        # Include invite link in envelope for API to return
        'invite_link': invite_link
    }

    return envelope


@response_handler('create_invite')
def create_invite_response(stored_ids: dict, params: dict, db: ReadOnlyConnection) -> dict:
    """Response handler for create_invite command."""
    # Get the invite that was just created
    invite_id = stored_ids.get('invite')

    if not invite_id:
        # No invite was stored, return empty result
        return {
            "ids": stored_ids,
            "data": {}
        }

    # Query the database to get the invite details
    # The invite_id is the event_id
    cursor = db.execute(
        "SELECT invite_secret, network_id, group_id FROM invites WHERE invite_id = ?",
        (invite_id,)
    )
    row = cursor.fetchone()

    if not row:
        # Invite not found in database
        return {
            "ids": stored_ids,
            "data": {}
        }

    invite_secret = row['invite_secret']
    network_id = row['network_id']
    group_id = row['group_id']

    # Create invite link data using the actual stored secret
    invite_data = {
        'invite_secret': invite_secret,
        'network_id': network_id,
        'group_id': group_id
    }

    # Encode invite link
    invite_json = json.dumps(invite_data)
    invite_code = base64.b64encode(invite_json.encode()).decode()
    invite_link = f"quiet://invite/{invite_code}"

    return {
        "ids": stored_ids,
        "data": {
            "invite_link": invite_link,  # Full link for convenience
            "invite_code": invite_code,  # Just the code for FE flexibility
            "invite_id": invite_id,
            "network_id": network_id,
            "group_id": group_id
        }
    }