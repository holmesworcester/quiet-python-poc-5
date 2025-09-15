"""
Commands for network event type.
"""
import time
from typing import Dict, Any, List
from core.crypto import generate_keypair
from core.core_types import command


@command
def create_network(params: Dict[str, Any]) -> List[dict[str, Any]]:
    """
    Create a new network.

    Returns a list of envelopes with network event and optionally identity event.
    """
    # Extract and validate parameters
    name = params.get('name', '')
    if not name:
        raise ValueError("name is required")

    # Check if we have an existing identity_id to use
    identity_id = params.get('identity_id')

    if identity_id:
        # Use existing identity
        creator_id = identity_id
        created_at = int(time.time() * 1000)

        # Create network event (unsigned)
        network_event: Dict[str, Any] = {
            'type': 'network',
            'network_id': '',  # Will be filled by encrypt handler
            'name': name,
            'creator_id': creator_id,
            'created_at': created_at,
            'signature': ''  # Will be filled by sign handler
        }

        # Create user event for the creator
        user_event: Dict[str, Any] = {
            'type': 'user',
            'user_id': creator_id,
            'network_id': '',  # Will be filled when network is created
            'username': params.get('username', 'Creator'),
            'created_at': created_at,
            'signature': ''  # Will be filled by sign handler
        }

        # Return network and user event envelopes
        return [
            {
                'event_plaintext': network_event,
                'event_type': 'network',
                'self_created': True,
                'peer_id': creator_id,
                'network_id': '',  # Will be filled by encrypt handler
                'deps': []  # Network creation doesn't depend on other events
            },
            {
                'event_plaintext': user_event,
                'event_type': 'user',
                'self_created': True,
                'peer_id': creator_id,
                'network_id': '',  # Will be filled when network is created
                'deps': ['network:']  # User depends on network existing
            }
        ]
    else:
        # Create new identity (backwards compatibility)
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
        envelopes: List[dict[str, Any]] = []

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