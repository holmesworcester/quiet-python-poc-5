"""
Commands for user actions.
"""
import time
from typing import Dict, Any, List
import sqlite3
from core.crypto import generate_keypair, hash as generate_hash


def join_network(params: Dict[str, Any], db: sqlite3.Connection) -> List[Dict[str, Any]]:
    """
    Join a network using an invite code.
    
    Params:
    - invite_code: The invite code to use
    - name: Optional name for the identity
    
    Plus these params that should be provided by the framework after validating the invite:
    - network_id: The network to join
    - inviter_id: The identity that created the invite
    
    Returns a list of envelopes to process.
    """
    if 'invite_code' not in params:
        raise ValueError("invite_code is required")
    if 'network_id' not in params:
        raise ValueError("network_id is required")
    if 'inviter_id' not in params:
        raise ValueError("inviter_id is required")
    
    # Generate keypair for new identity
    private_key, public_key = generate_keypair()
    peer_id = public_key.hex()
    
    # Create identity event (unsigned)
    event = {
        'type': 'identity',
        'peer_id': peer_id,
        'network_id': params['network_id'],
        'invited_by': params['inviter_id'],
        'invite_code': params['invite_code'],
        'name': params.get('name', f'User-{peer_id[:8]}'),
        'created_at': int(time.time() * 1000)
    }
    
    # Return the event as an envelope
    envelope = {
        'event_plaintext': event,
        'event_type': 'identity',
        'self_created': True,
        'peer_id': peer_id,
        'network_id': params['network_id'],
        'deps': [],  # Identity events are self-signing
        # Local-only metadata for framework to store
        'local_metadata': {
            'private_key': private_key.hex(),
            'public_key': public_key.hex()
        }
    }
    
    return [envelope]


def create_user(params: Dict[str, Any], db: sqlite3.Connection) -> List[Dict[str, Any]]:
    """
    Create a user event when joining a network.
    
    This is typically called after creating an identity to establish
    the user's presence in the network.
    
    Required params:
    - identity_id: The identity creating the user event
    - address: Initial network address (can be placeholder like "0.0.0.0")
    - port: Initial port (can be 0 for not listening)
    
    Returns a user event establishing network presence.
    """
    identity_id = params.get('identity_id')
    address = params.get('address', '0.0.0.0')  # Default placeholder
    port = params.get('port', 0)  # Default no listening
    
    if not identity_id:
        raise ValueError("identity_id is required")
    
    # Get identity info
    cursor = db.execute(
        "SELECT identity_id, network_id FROM identities WHERE identity_id = ?",
        (identity_id,)
    )
    identity = cursor.fetchone()
    if not identity:
        raise ValueError(f"Identity not found: {identity_id}")
    
    peer_id = identity['identity_id']
    network_id = identity['network_id']
    
    # Generate user_id 
    created_at = int(time.time() * 1000)
    user_id = generate_hash(f"user:{peer_id}:{network_id}:{created_at}".encode()).hex()
    
    # Create user event (unsigned)
    event = {
        'type': 'user',
        'user_id': user_id,
        'peer_id': peer_id,
        'network_id': network_id,
        'address': address,
        'port': int(port),
        'created_at': created_at,
        'signature': ''  # Will be filled by sign handler
    }
    
    # Create envelope
    envelope = {
        'event_plaintext': event,
        'event_type': 'user',
        'self_created': True,
        'peer_id': peer_id,
        'network_id': network_id,
        'deps': [f"identity:{peer_id}"]  # Depends on identity existing
    }
    
    return [envelope]