"""
Commands for identity event type.
"""
import time
from typing import Dict, Any
from core.crypto import generate_keypair
from core.core_types import command


@command
def create_identity(params: Dict[str, Any]) -> dict[str, Any]:
    """
    Create a new identity.
    
    Returns an envelope with unsigned identity event.
    """
    # Extract parameters
    network_id = params.get('network_id', '')
    name = params.get('name', 'User')
        
    # Generate keypair
    private_key, public_key = generate_keypair()
    peer_id = public_key.hex()
    
    # Create identity event (local-only, not signed or shared)
    event: Dict[str, Any] = {
        'type': 'identity',
        'name': name,
        'network_id': network_id,
        'public_key': public_key.hex(),
        'created_at': int(time.time() * 1000)
        # No signature field - identity events are local-only
    }

    # Calculate identity_id as hash of the event
    import json as json_module
    from core.crypto import hash as crypto_hash
    canonical_identity = json_module.dumps(event, sort_keys=True).encode()
    identity_id = crypto_hash(canonical_identity, size=16).hex()

    # Return the event as an envelope
    envelope = {
        'event_plaintext': event,
        'event_type': 'identity',
        'event_id': identity_id,  # Pre-calculated since not signed
        'self_created': True,
        'validated': True,  # Identity events are local-only, immediately valid
        'network_id': network_id,
        'deps': [],  # Identity events have no dependencies
        'deps_included_and_valid': True,  # No deps to check
        # Store the secret (private key) - not shared
        'secret': {
            'private_key': private_key.hex(),
            'public_key': public_key.hex()
        }
    }

    return envelope