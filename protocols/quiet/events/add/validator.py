"""
Validator for add events.
"""
from typing import Dict, Any


def validate(event_data: Dict[str, Any], metadata: Dict[str, Any]) -> bool:
    """
    Validate an add event.
    
    Returns True if valid, False if invalid.
    """
    # Check type
    if event_data.get('type') != 'add':
        return False
        
    # Check required fields
    required_fields = ['group_id', 'user_id', 'added_by', 'network_id', 'created_at']
    for field in required_fields:
        if field not in event_data:
            return False
    
    # Check added_by matches peer_id (the signer)
    if event_data['added_by'] != metadata.get('peer_id'):
        return False
    
    # Check that user_id and group_id are not empty
    if not event_data['user_id'] or not event_data['group_id']:
        return False
    
    # TODO: In a full implementation, we'd check:
    # - If the group exists
    # - If the added_by user has permission to add members
    # - If the user_id is valid
    
    return True