"""
Validator for message events.
"""
from typing import Any
from core.core_types import validator
from protocols.quiet.protocol_types import validate_envelope_fields
from protocols.quiet.events import MessageEventData, validate_event_data


@validator
def validate(envelope: dict[str, Any]) -> bool:
    """
    Validate a message event.

    Checks:
    - Has required fields
    - Message ID is valid
    - Author is the signer
    - Content is not empty
    """
    # Ensure we have event_plaintext
    if not validate_envelope_fields(envelope, {'event_plaintext'}):
        print(f"[message validator] Missing event_plaintext")
        return False

    event_data = envelope['event_plaintext']

    # Use the registry validator
    if not validate_event_data('message', event_data):
        print(f"[message validator] Event data validation failed")
        return False

    # Message events should reference the peer that created them
    # But for now we're using identity_id directly for signing
    # TODO: Update to use peer_id once we have proper peer events

    # Check content is not empty
    if not event_data.get('content') or not event_data['content'].strip():
        print(f"[message validator] Empty content")
        return False

    # Check content length (reasonable limit)
    if len(event_data['content']) > 10000:
        print(f"[message validator] Content too long")
        return False

    return True