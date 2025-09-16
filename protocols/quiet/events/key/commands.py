"""
Commands for key event type.
"""
import time
from typing import Dict, Any
from core.crypto import generate_secret, seal, generate_keypair
from core.core_types import command
from protocols.quiet.client import CreateKeyParams, CommandResponse


@command(param_type=CreateKeyParams, result_type=CommandResponse)
def create_key(params: Dict[str, Any]) -> dict[str, Any]:
    """
    Create a new encryption key for a group.
    
    Returns an envelope with unsigned key event.
    """
    # Extract parameters
    group_id = params.get('group_id', '')
    network_id = params.get('network_id', '')
    identity_id = params.get('identity_id', '')
    
    # Generate a temporary keypair for key generation
    # In production, this would use the identity's actual public key
    private_key, public_key = generate_keypair()
    peer_id = identity_id
    
    # Generate a random encryption key
    secret = generate_secret()
    
    # Seal the secret with our public key (so we can decrypt it later)
    sealed_secret = seal(secret, public_key)
    
    # Create key event (unsigned)
    event: Dict[str, Any] = {
        'type': 'key',
        'key_id': '',  # Will be filled by encrypt handler
        'peer_id': peer_id,
        'group_id': group_id,
        'sealed_secret': sealed_secret.hex(),
        'network_id': network_id,
        'created_at': int(time.time() * 1000),
        'signature': ''  # Will be filled by sign handler
    }
    
    # Create envelope
    envelope: dict[str, Any] = {
        'event_plaintext': event,
        'event_type': 'key',
        'self_created': True,
        'peer_id': peer_id,
        'network_id': network_id,
        'deps': [f"group:{group_id}"]  # Key depends on group existing
    }
    
    return envelope
