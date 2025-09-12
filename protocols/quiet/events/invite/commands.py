"""
Commands for invite event type.
"""
import time
import secrets
from typing import Dict, Any, List
import sqlite3


def create_invite(params: Dict[str, Any], db: sqlite3.Connection) -> List[Dict[str, Any]]:
    """
    Create a new invite to join a network.
    
    Params:
    - network_id: The network to create an invite for
    - identity_id: The identity creating the invite
    - invite_code: Optional invite code (generated if not provided)
    - expires_in_days: Optional expiration in days (default 7)
    
    Returns a list of envelopes to process.
    """
    if 'network_id' not in params:
        raise ValueError("network_id is required")
    if 'identity_id' not in params:
        raise ValueError("identity_id is required")
    
    # Get identity info
    cursor = db.execute(
        "SELECT identity_id as peer_id FROM identities WHERE identity_id = ?",
        (params['identity_id'],)
    )
    identity = cursor.fetchone()
    if not identity:
        raise ValueError(f"Identity not found: {params['identity_id']}")
    
    peer_id = identity['peer_id']
    
    # Generate invite code if not provided
    invite_code = params.get('invite_code', secrets.token_urlsafe(32))
    
    # Calculate expiration
    expires_in_days = params.get('expires_in_days', 7)
    expires_at = int(time.time() * 1000) + expires_in_days * 24 * 60 * 60 * 1000
    
    # Create invite event (unsigned)
    event = {
        'type': 'invite',
        'invite_code': invite_code,
        'network_id': params['network_id'],
        'inviter_id': peer_id,
        'created_at': int(time.time() * 1000),
        'expires_at': expires_at
    }
    
    # Return the event as an envelope
    envelope = {
        'event_plaintext': event,
        'event_type': 'invite',
        'self_created': True,
        'peer_id': peer_id,
        'network_id': params['network_id'],
        'deps': []  # Invites don't depend on other events
    }
    
    return [envelope]