"""
Commands for network event type.
"""
import time
from typing import Dict, Any, List
from core.crypto import generate_keypair
from core.types import Envelope, command


@command 
def create_network(params: Dict[str, Any]) -> List[Envelope]:
    """
    Create a new network.
    
    Returns a list of envelopes with identity and network events.
    """
    # Extract parameters
    name = params.get('name', '')
    description = params.get('description', '')
    creator_name = params.get('creator_name', 'Network Creator')
    
    # Generate keypair for network creator identity
    private_key, public_key = generate_keypair()
    creator_id = public_key.hex()
    
    created_at = int(time.time() * 1000)
    
    # Create network event (unsigned)
    network_event: Dict[str, Any] = {
        'type': 'network',
        'network_id': '',  # Will be filled by encrypt handler
        'name': name,
        'description': description,
        'creator_id': creator_id,
        'created_at': created_at,
        'signature': ''  # Will be filled by sign handler
    }
    
    # Identity event for the creator (unsigned)
    identity_event: Dict[str, Any] = {
        'type': 'identity',
        'peer_id': creator_id,
        'network_id': '',  # Will be filled when network event is processed
        'name': creator_name,
        'created_at': created_at,
        'signature': ''  # Will be filled by sign handler
    }
    
    # Return both the identity and network event envelopes
    envelopes: List[Envelope] = []
    
    # Identity event MUST come first so it can be processed and store the signing key
    # before the network event needs to be signed
    envelopes.append({
        'event_plaintext': identity_event,
        'event_type': 'identity',
        'self_created': True,
        'peer_id': creator_id,
        'network_id': '',  # Will be filled when network event is processed
        'deps': [],  # Identity doesn't depend on other events (self-signing)
        # Store the secret (private key) - this won't be shared
        'secret': {
            'private_key': private_key.hex(),
            'public_key': public_key.hex()
        }
    })
    
    # Network event envelope - comes after identity so signing key is available
    envelopes.append({
        'event_plaintext': network_event,
        'event_type': 'network',
        'self_created': True,
        'peer_id': creator_id,
        'network_id': '',  # Will be filled by encrypt handler
        'deps': []  # Network creation doesn't depend on other events
    })
    
    return envelopes