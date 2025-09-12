"""
Commands for identity event type.
"""
import time
from typing import Dict, Any
from core.crypto import generate_keypair
from core.types import Envelope, command
from protocols.quiet.events import CreateIdentityParams


@command
def create_identity(params: Dict[str, Any]) -> Envelope:
    """
    Create a new identity.
    
    Params:
    - network_id: The network this identity is for
    - name: Name for the identity
    
    Returns an envelope with unsigned identity event.
    """
    # Validate parameters
    try:
        cmd_params = CreateIdentityParams(
            name=params.get('name', 'User'),
            network_id=params['network_id']
        )
    except (KeyError, TypeError) as e:
        raise ValueError(f"Invalid parameters: {e}")
        
    # Generate keypair
    private_key, public_key = generate_keypair()
    peer_id = public_key.hex()
    
    # Create identity event (unsigned)
    event: dict[str, Any] = {
        'type': 'identity',
        'peer_id': peer_id,
        'network_id': cmd_params.network_id,
        'name': cmd_params.name,
        'created_at': int(time.time() * 1000),
        'signature': ''  # Will be filled by sign handler
    }
    
    # Return the event as an envelope
    # For identity, we don't need deps since it's self-signing
    envelope: Envelope = {
        'event_plaintext': event,
        'event_type': 'identity',
        'self_created': True,
        'peer_id': peer_id,
        'network_id': cmd_params.network_id,
        'deps': [],  # Identity events have no dependencies
        # Store the secret (private key) - this won't be shared
        'secret': {
            'private_key': private_key.hex(),
            'public_key': public_key.hex()
        }
    }
    
    return envelope