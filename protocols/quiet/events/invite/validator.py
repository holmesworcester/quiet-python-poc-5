"""
Validator for invite events.
"""
from typing import Dict, Any


def validate(event_data: Dict[str, Any], metadata: Dict[str, Any]) -> bool:
    """
    Validate an invite event.
    
    Returns True if valid, False if invalid.
    """
    # Check type
    if event_data.get('type') != 'invite':
        return False
        
    # Check required fields
    required_fields = ['invite_code', 'network_id', 'inviter_id', 'created_at', 'expires_at']
    for field in required_fields:
        if field not in event_data:
            return False
    
    # Check that invite_code is not empty
    if not event_data['invite_code'].strip():
        return False
    
    # Check that expiration is in the future (when created)
    if event_data['expires_at'] <= event_data['created_at']:
        return False
    
    # Check inviter matches peer_id (the signer)
    if event_data['inviter_id'] != metadata.get('peer_id'):
        return False
    
    return True