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
            'network_id': '@generated:network:0',  # Reference to the network we're creating
            'username': params.get('username', 'Creator'),
            'created_at': created_at,
            'signature': ''  # Will be filled by sign handler
        }

        # Create default group
        default_group_name = params.get('default_group_name', 'General')
        group_event: Dict[str, Any] = {
            'type': 'group',
            'group_id': '',  # Will be filled by encrypt handler
            'network_id': '@generated:network:0',  # Reference to the network we're creating
            'name': default_group_name,
            'creator_id': creator_id,
            'created_at': created_at,
            'signature': ''  # Will be filled by sign handler
        }

        # Create default channel in the default group
        default_channel_name = params.get('default_channel_name', 'general')
        channel_event: Dict[str, Any] = {
            'type': 'channel',
            'channel_id': '',  # Will be filled by encrypt handler
            'group_id': '@generated:group:0',  # Reference to the group we're creating
            'network_id': '@generated:network:0',  # Reference to the network we're creating
            'name': default_channel_name,
            'creator_id': creator_id,
            'created_at': created_at,
            'signature': ''  # Will be filled by sign handler
        }

        # Return network, user, group, and channel event envelopes
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
                'deps': ['@generated:network:0']  # User depends on the network we're creating
            },
            {
                'event_plaintext': group_event,
                'event_type': 'group',
                'self_created': True,
                'peer_id': creator_id,
                'network_id': '',  # Will be filled when network is created
                'deps': ['@generated:network:0']  # Group depends on the network we're creating
            },
            {
                'event_plaintext': channel_event,
                'event_type': 'channel',
                'self_created': True,
                'peer_id': creator_id,
                'network_id': '',  # Will be filled when network is created
                'deps': ['@generated:group:0']  # Channel depends on the group
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