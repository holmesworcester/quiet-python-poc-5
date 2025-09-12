"""
Commands for network event type.
"""
import time
import secrets
from typing import Dict, Any, List
import sqlite3
from core.crypto import generate_keypair


def create_network(params: Dict[str, Any], db: sqlite3.Connection) -> List[Dict[str, Any]]:
    """
    Create a new network.
    
    Params:
    - name: The name of the network
    - description: Optional description of the network
    - creator_name: Optional name for the creator identity
    
    Returns a list of envelopes to process.
    """
    if 'name' not in params:
        raise ValueError("name is required")
    
    # Generate a network ID
    network_id = secrets.token_urlsafe(16)
    
    # Generate keypair for network creator identity
    private_key, public_key = generate_keypair()
    creator_id = public_key.hex()
    
    # Create network event (unsigned)
    event = {
        'type': 'network',
        'network_id': network_id,
        'name': params['name'],
        'description': params.get('description', ''),
        'creator_id': creator_id,
        'created_at': int(time.time() * 1000)
    }
    
    # Return both the network event and identity event
    envelopes = []
    
    # Identity event MUST come first so it can be processed and store the signing key
    # before the network event needs to be signed
    
    # Identity event for the creator (unsigned)
    identity_event = {
        'type': 'identity',
        'peer_id': creator_id,
        'network_id': network_id,
        'name': params.get('creator_name', 'Network Creator'),
        'created_at': event['created_at']
    }
    
    envelopes.append({
        'event_plaintext': identity_event,
        'event_type': 'identity',
        'self_created': True,
        'peer_id': creator_id,
        'network_id': network_id,
        'deps': [],  # Identity doesn't depend on other events (self-signing)
        # Local-only metadata for framework to store
        'local_metadata': {
            'private_key': private_key.hex(),
            'public_key': public_key.hex()
        }
    })
    
    # Network event envelope - comes after identity so signing key is available
    envelopes.append({
        'event_plaintext': event,
        'event_type': 'network',
        'self_created': True,
        'peer_id': creator_id,
        'network_id': network_id,
        'deps': []  # Network creation doesn't depend on other events
    })
    
    return envelopes