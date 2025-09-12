"""
Commands for user actions.
"""
import time
from typing import Dict, Any, List
import sqlite3
from core.crypto import generate_keypair


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