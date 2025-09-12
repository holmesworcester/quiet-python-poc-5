"""
Check Group Membership handler - Validates group membership for group events.

From plan.md:
- Filter: event_plaintext has `group_id` AND `is_group_member` is false/absent
- Validates: group_member_id matches user_id and group_id
- Output Type: Same with `is_group_member: true`
"""

from core.types import Envelope


def filter_func(envelope: Envelope) -> bool:
    """
    Process envelopes that have group_id in plaintext but haven't been checked for membership.
    """
    event_plaintext = envelope.get('event_plaintext', {})
    return (
        'group_id' in event_plaintext and
        envelope.get('is_group_member') is not True
    )


def handler(envelope: Envelope) -> Envelope:
    """
    Check if the event author is a valid member of the group.
    
    Args:
        envelope: Envelope with event_plaintext containing group_id
        
    Returns:
        Envelope with is_group_member: true if valid, or error if not
    """
    # TODO: Implement actual group membership validation
    # For now, stub implementation that approves all
    
    event_plaintext = envelope['event_plaintext']
    group_id = event_plaintext.get('group_id')
    group_member_id = event_plaintext.get('group_member_id')
    user_id = event_plaintext.get('user_id')
    
    # Would normally:
    # 1. Look up group membership from resolved_deps or database
    # 2. Verify that group_member_id is valid for this group_id
    # 3. Verify that user_id matches the group_member's user_id
    # 4. Check any other group-specific rules
    
    # Stub: Always approve for now
    envelope['is_group_member'] = True
    
    # If validation failed, we would set an error instead:
    # envelope['error'] = f"User {user_id} is not a member of group {group_id}"
    
    return envelope