"""
Validator for key events.
"""
from typing import Dict, Any


def validate(event_data: Dict[str, Any], envelope_metadata: Dict[str, Any]) -> bool:
    """
    Validate a key event.
    - Must have key_id (hash of the key event)
    - Must have group_id
    - Must have sealed_secret (encrypted with peer's public key)
    - Must have peer_id
    - Signature validation is handled by the framework
    """
    if 'type' not in event_data or event_data['type'] != 'key':
        return False
        
    required_fields = ['key_id', 'group_id', 'sealed_secret', 'peer_id']
    for field in required_fields:
        if field not in event_data:
            return False
            
    # Additional validation
    if not event_data['key_id'] or len(event_data['key_id']) != 64:  # 32 bytes hex
        return False
        
    if not event_data['sealed_secret']:
        return False
        
    return True