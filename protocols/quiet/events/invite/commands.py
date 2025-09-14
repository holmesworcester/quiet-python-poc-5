"""
Commands for invite event type.
"""
import time
import secrets
from typing import Dict, Any
from core.types import Envelope, command


@command
def create_invite(params: Dict[str, Any]) -> Envelope:
    """
    Create a new invite to join a network.
    
    Returns an envelope with unsigned invite event.
    """
    # Extract parameters
    network_id = params.get('network_id', '')
    identity_id = params.get('identity_id', '')
    invite_code = params.get('invite_code', secrets.token_urlsafe(32))
    expires_in_days = params.get('expires_in_days', 7)
    
    # Calculate expiration
    expires_at = int(time.time() * 1000) + expires_in_days * 24 * 60 * 60 * 1000
    
    # Create invite event (unsigned)
    event: Dict[str, Any] = {
        'type': 'invite',
        'invite_code': invite_code,
        'network_id': network_id,
        'inviter_id': identity_id,
        'created_at': int(time.time() * 1000),
        'expires_at': expires_at,
        'signature': ''  # Will be filled by sign handler
    }
    
    # Create envelope
    envelope: Envelope = {
        'event_plaintext': event,
        'event_type': 'invite',
        'self_created': True,
        'peer_id': identity_id,
        'network_id': network_id,
        'deps': []  # Invites don't depend on other events
    }
    
    return envelope