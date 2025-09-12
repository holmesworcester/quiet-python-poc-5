"""
Validator for group events.
"""
from typing import Dict, Any


def validate(event_data: Dict[str, Any], metadata: Dict[str, Any]) -> bool:
    """
    Validate a group event.
    
    Checks:
    - Has required fields
    - Group ID is valid
    - Creator is the signer
    - Permissions are valid
    """
    # Check required fields
    required = ['type', 'group_id', 'name', 'network_id', 'creator_id', 'created_at', 'permissions']
    for field in required:
        if field not in event_data:
            return False
    
    # Check type
    if event_data['type'] != 'group':
        return False
    
    # Check creator matches peer_id (the signer)
    if event_data['creator_id'] != metadata.get('peer_id'):
        return False
    
    # Check permissions structure
    perms = event_data.get('permissions', {})
    if not isinstance(perms, dict):
        return False
    
    # Basic permission validation
    valid_perms = ['invite', 'remove', 'message']
    for perm in perms:
        if perm not in valid_perms:
            return False
    
    return True