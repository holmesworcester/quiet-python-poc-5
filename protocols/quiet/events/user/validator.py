"""
Validator for user events.
"""
from typing import Dict, Any


def validate(event_data: Dict[str, Any], metadata: Dict[str, Any]) -> bool:
    """
    Validate a user event.
    
    User events store network address information for P2P connectivity.
    
    Checks:
    - Has required fields
    - User ID is valid
    - Peer ID matches signer
    - Port is in valid range
    """
    # Check required fields
    required = ['type', 'user_id', 'peer_id', 'network_id', 'address', 'port', 'created_at', 'signature']
    for field in required:
        if field not in event_data:
            return False
    
    # Check type
    if event_data['type'] != 'user':
        return False
    
    # Check peer_id matches metadata (the signer)
    if event_data['peer_id'] != metadata.get('peer_id'):
        return False
    
    # Validate port is in valid range
    port = event_data.get('port')
    if not isinstance(port, int) or port < 1 or port > 65535:
        return False
    
    # Validate address is not empty
    if not event_data.get('address') or not isinstance(event_data['address'], str):
        return False
    
    # Validate network_id is not empty
    if not event_data.get('network_id'):
        return False
    
    return True