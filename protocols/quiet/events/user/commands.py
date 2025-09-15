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

    Returns envelopes for identity, peer, and user events.
    """
    # Extract parameters
    invite_link = params.get('invite_link', '')
    name = params.get('name', '')

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

    # Generate keypair for new identity
    private_key, public_key = generate_keypair()

    # Use generated name if not provided
    if not name:
        name = f'User-{public_key.hex()[:8]}'

    # Derive invite pubkey from secret (same as create_invite)
    invite_salt = hashlib.sha256(b"quiet_invite_kdf_v1").digest()[:16]
    derived_key = kdf(invite_secret.encode(), salt=invite_salt)
    invite_pubkey = derived_key.hex()

    envelopes = []

    # 1. Create identity event (local-only, not signed or shared)
    # Don't include identity_id in the event - it's the hash
    identity_event: Dict[str, Any] = {
        'type': 'identity',
        'name': name,
        'network_id': network_id,
        'public_key': public_key.hex(),  # Store public key in event
        'created_at': int(time.time() * 1000)
        # No signature field - identity events are local-only
    }

    # Calculate identity_id as hash of the event (since it's not signed)
    canonical_identity = json_module.dumps(identity_event, sort_keys=True).encode()
    identity_id = crypto_hash(canonical_identity, size=16).hex()

    # Create invite signature to prove we have the secret
    invite_sig_data = f"{invite_secret}:{public_key.hex()}:{network_id}"
    invite_signature = crypto_hash(invite_sig_data.encode()).hex()[:64]  # Use hash as proof, as hex string

    envelopes.append({
        'event_plaintext': identity_event,
        'event_type': 'identity',
        'event_id': identity_id,  # Pre-calculated since not signed
        'self_created': True,
        'validated': True,  # Identity events are local-only, immediately valid
        'write_to_store': True,  # Should be stored
        'network_id': network_id,
        'deps': [],  # Identity has no dependencies
        'deps_included_and_valid': True,  # No deps to check
        # Store the secret (private key) - not shared
        'secret': {
            'private_key': private_key.hex(),
            'public_key': public_key.hex()
        }
    })

    # 2. Create peer event (identity on this device)
    peer_event: Dict[str, Any] = {
        'type': 'peer',
        'public_key': public_key.hex(),  # The identity's public key
        'identity_id': identity_id,  # Reference to the identity
        'network_id': network_id,
        'created_at': int(time.time() * 1000),
        'signature': ''  # Will be filled by sign handler
    }

    envelopes.append({
        'event_plaintext': peer_event,
        'event_type': 'peer',
        'self_created': True,
        'peer_id': public_key.hex(),  # Signed by this public key
        'network_id': network_id,
        'deps': [f"identity:{identity_id}"]  # Depends on identity
    })

    # 3. Create user event (account via invite)
    # The peer_id in the event is the peer creating this user
    # Use placeholder that will be resolved to the peer event's hash
    user_event: Dict[str, Any] = {
        'type': 'user',
        'peer_id': '@generated:peer:0',  # Placeholder for first peer event's ID
        'network_id': network_id,
        'group_id': group_id,  # From invite
        'name': name,
        'invite_pubkey': invite_pubkey,  # Proves we have the invite
        'invite_signature': invite_signature,
        'created_at': int(time.time() * 1000),
        'signature': ''  # Will be filled by sign handler
    }

    envelopes.append({
        'event_plaintext': user_event,
        'event_type': 'user',
        'self_created': True,
        'peer_id': public_key.hex(),  # Signed by this public key
        'network_id': network_id,
        'deps': [
            '@generated:peer:0',  # Depends on peer existing (placeholder)
            f"invite:{invite_pubkey}"  # Depends on invite existing
        ]
    })

    return envelopes


@command
def create_user(params: Dict[str, Any]) -> dict[str, Any]:
    """
    Create a user event when joining a network.
    
    Returns an envelope with unsigned user event.
    """
    # Extract parameters
    identity_id = params.get('identity_id', '')
    network_id = params.get('network_id', '')
    address = params.get('address', '0.0.0.0')  # Default placeholder
    port = params.get('port', 0)  # Default no listening
    
    # Create user event (unsigned)
    event: Dict[str, Any] = {
        'type': 'user',
        'user_id': '',  # Will be filled by encrypt handler
        'peer_id': identity_id,
        'network_id': network_id,
        'address': address,
        'port': int(port),
        'created_at': int(time.time() * 1000),
        'signature': ''  # Will be filled by sign handler
    }
    
    # Create envelope
    envelope: dict[str, Any] = {
        'event_plaintext': event,
        'event_type': 'user',
        'self_created': True,
        'peer_id': identity_id,
        'network_id': network_id,
        'deps': [f"identity:{identity_id}"]  # Depends on identity existing
    }
    
    return envelope