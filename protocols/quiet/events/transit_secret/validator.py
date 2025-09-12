"""
Validator for transit secret events.
"""
from typing import Dict, Any


def validate(event_data: Dict[str, Any], envelope_metadata: Dict[str, Any]) -> bool:
    """
    Validate a transit secret event.
    - Must have transit_key_id
    - Must have network_id
    - Must have peer_id
    - Secret is NOT included (kept local only)
    - Signature validation is handled by the framework
    """
    if 'type' not in event_data or event_data['type'] != 'transit_secret':
        return False
        
    required_fields = ['transit_key_id', 'network_id', 'peer_id']
    for field in required_fields:
        if field not in event_data:
            return False
            
    # Additional validation
    if not event_data['transit_key_id'] or len(event_data['transit_key_id']) != 64:  # 32 bytes hex
        return False
        
    return True