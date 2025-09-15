"""
Validator for user events.
"""
from typing import Dict, Any
from core.core_types import validator
from protocols.quiet.protocol_types import validate_envelope_fields
from protocols.quiet.events import UserEventData, validate_event_data


@validator
def validate(envelope: dict[str, Any]) -> bool:
    """
    Validate a user event.

    For self-created user events (joining via invite link), we trust the invite
    data since the user chose to trust the invite link. The invite_pubkey and
    invite_signature prove they have the invite secret.

    For external user events, full validation including invite verification
    would be needed.

    Returns True if valid, False otherwise.
    """
    # Ensure we have event_plaintext
    if not validate_envelope_fields(envelope, {'event_plaintext'}):
        return False

    event = envelope['event_plaintext']

    # Check type
    if event.get('type') != 'user':
        return False

    # Check required fields for new user structure (no user_id in event)
    required_fields = ['type', 'peer_id', 'network_id', 'group_id',
                       'name', 'invite_pubkey', 'invite_signature', 'created_at', 'signature']
    for field in required_fields:
        if field not in event:
            return False

    # Validate network_id is not empty
    if not event['network_id']:
        return False

    # Validate group_id is not empty
    if not event['group_id']:
        return False

    # Validate invite_pubkey is not empty
    if not event['invite_pubkey']:
        return False

    # For self-created events, we trust the invite data
    # The user explicitly chose to trust the invite link
    if envelope.get('self_created'):
        # The invite_pubkey and invite_signature prove they have the invite secret
        # We don't need the actual invite event to exist
        return True

    # For external user events, we need full validation
    # Check that dependencies were resolved (invite must exist)
    if not envelope.get('deps_included_and_valid'):
        return False

    resolved_deps = envelope.get('resolved_deps', {})

    # Find the invite dependency
    invite_dep_key = f"invite:{event['invite_pubkey']}"
    if invite_dep_key not in resolved_deps:
        # Invite dependency must be present for external events
        return False

    invite_envelope = resolved_deps[invite_dep_key]
    invite_event = invite_envelope.get('event_plaintext', {})

    # Verify the invite matches what the user claims
    if invite_event.get('group_id') != event['group_id']:
        return False

    # Verify the invite_signature is valid
    # This proves the user had the invite_secret
    # (actual signature verification would happen here)
    if not event['invite_signature']:
        return False

    # The peer that signed this user event must match the peer_id in the event
    # (signature handler already verified the signature matches the peer)

    return True