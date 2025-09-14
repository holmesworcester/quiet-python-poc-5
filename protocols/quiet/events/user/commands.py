"""
Commands for user actions.
"""
import time
from typing import Dict, Any
from core.crypto import generate_keypair
from core.types import Envelope, command


@command
def join_network(params: Dict[str, Any]) -> Envelope:
    """
    Join a network using an invite code.
    
    Returns an envelope with unsigned identity event.
    """
    # Extract parameters
    invite_code = params.get('invite_code', '')
    network_id = params.get('network_id', '')
    inviter_id = params.get('inviter_id', '')
    name = params.get('name', '')
    
    # Generate keypair for new identity
    private_key, public_key = generate_keypair()
    peer_id = public_key.hex()
    
    # Use generated name if not provided
    if not name:
        name = f'User-{peer_id[:8]}'
    
    # Create identity event (unsigned)
    event: Dict[str, Any] = {
        'type': 'identity',
        'peer_id': peer_id,
        'network_id': network_id,
        'invited_by': inviter_id,
        'invite_code': invite_code,
        'name': name,
        'created_at': int(time.time() * 1000),
        'signature': ''  # Will be filled by sign handler
    }
    
    # Return the event as an envelope
    envelope: Envelope = {
        'event_plaintext': event,
        'event_type': 'identity',
        'self_created': True,
        'peer_id': peer_id,
        'network_id': network_id,
        'deps': [],  # Identity events are self-signing
        # Store the secret (private key) - this won't be shared
        'secret': {
            'private_key': private_key.hex(),
            'public_key': public_key.hex()
        }
    }
    
    return envelope


@command
def create_user(params: Dict[str, Any]) -> Envelope:
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
    envelope: Envelope = {
        'event_plaintext': event,
        'event_type': 'user',
        'self_created': True,
        'peer_id': identity_id,
        'network_id': network_id,
        'deps': [f"identity:{identity_id}"]  # Depends on identity existing
    }
    
    return envelope