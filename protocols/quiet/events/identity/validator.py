"""
Validator for identity events (local-only).
"""
from typing import Dict, Any
from core.core_types import validator


@validator
def validate(envelope: Dict[str, Any]) -> bool:
    event = envelope.get('event_plaintext', {})

    if event.get('type') != 'identity':
        return False

    required = ['identity_id', 'name', 'public_key', 'private_key', 'created_at']
    for f in required:
        if f not in event:
            return False

    # Mark identity as self-created/local-only via flags in the envelope
    return True

