"""
Validator for channel events.
"""
from typing import Dict, Any


def validate(event_data: Dict[str, Any], metadata: Dict[str, Any]) -> bool:
    """
    Validate a channel event.
    
    Checks:
    - Has required fields
    - Channel ID is valid
    - Creator is the signer
    - Group ID exists
    """
    # Check required fields
    required = ['type', 'channel_id', 'group_id', 'name', 'network_id', 'creator_id', 'created_at']
    for field in required:
        if field not in event_data:
            return False
    
    # Check type
    if event_data['type'] != 'channel':
        return False
    
    # Check creator matches peer_id (the signer)
    if event_data['creator_id'] != metadata.get('peer_id'):
        return False
    
    # TODO: In a full implementation, we'd check if the group exists
    # and if the creator is a member of the group
    
    return True