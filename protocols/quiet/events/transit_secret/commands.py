"""
Commands for transit secret event type.
"""
import time
from typing import Dict, Any
from core.crypto import generate_secret
from core.types import Envelope, command


@command
def create_transit_secret(params: Dict[str, Any]) -> Envelope:
    """
    Create a new transit encryption key.
    
    Returns an envelope with unsigned transit secret event.
    """
    # Extract parameters
    network_id = params.get('network_id', '')
    identity_id = params.get('identity_id', '')
    
    # Generate a random transit key
    secret = generate_secret()
    
    # Create transit secret event (unsigned)
    event: Dict[str, Any] = {
        'type': 'transit_secret',
        'transit_key_id': '',  # Will be filled by encrypt handler
        'peer_id': identity_id,
        'network_id': network_id,
        'created_at': int(time.time() * 1000),
        'signature': ''  # Will be filled by sign handler
    }
    
    # Create envelope
    envelope: Envelope = {
        'event_plaintext': event,
        'event_type': 'transit_secret',
        'self_created': True,
        'peer_id': identity_id,
        'network_id': network_id,
        'deps': [],  # Transit secrets don't depend on other events
        # Store the secret - this won't be shared
        'secret': {
            'transit_key': secret.hex()
        }
    }
    
    return envelope