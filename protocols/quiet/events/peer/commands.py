"""
Commands for peer event type.
"""
import time
import hashlib
from typing import Dict, Any
from core.core_types import command


@command
def create_peer(params: Dict[str, Any]) -> dict[str, Any]:
    """
    Create a peer event representing an identity on a specific device.
    The peer IS the combination of identity + device.

    Returns an envelope with unsigned peer event.
    """
    # Extract parameters
    public_key = params.get('public_key', '')  # The identity's public key
    identity_id = params.get('identity_id', '')  # Hash of identity event
    network_id = params.get('network_id', '')

    # Create peer event (unsigned)
    # peer_id will be filled by handler as hash of the event
    event: Dict[str, Any] = {
        'type': 'peer',
        'public_key': public_key,  # The identity's public key
        'identity_id': identity_id,  # Reference to identity event
        'network_id': network_id,
        'created_at': int(time.time() * 1000),
        'signature': ''  # Will be filled by sign handler
    }

    # Create envelope
    envelope: dict[str, Any] = {
        'event_plaintext': event,
        'event_type': 'peer',
        'self_created': True,
        'peer_id': public_key,  # Signed by this public key
        'network_id': network_id,
        'deps': [f"identity:{identity_id}"]  # Depends on identity existing
    }

    return envelope