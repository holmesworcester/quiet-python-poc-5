"""Validator for sync request events."""

from typing import Dict, Any
from core.core_types import validator


@validator
def validate(envelope: Dict[str, Any]) -> bool:
    """
    Validate a sync request event.

    Sync requests are ephemeral and have relaxed validation since
    they're not stored permanently.

    Returns:
        True if valid, False if invalid
    """
    event_data = envelope.get('event_plaintext', {})

    # Check type
    if event_data.get('type') != 'sync_request':
        return False

    # Check required fields
    required_fields = ['type', 'request_id', 'network_id', 'peer_id', 'timestamp_ms']
    for field in required_fields:
        if field not in event_data:
            return False

    # Check that IDs are not empty
    if not event_data['request_id']:
        return False

    if not event_data['network_id']:
        return False

    if not event_data['peer_id']:
        return False

    # Validate timestamp is reasonable
    timestamp = event_data.get('timestamp_ms', 0)
    if not isinstance(timestamp, int) or timestamp <= 0:
        return False

    # Transit secret is optional but if present should be non-empty
    transit_secret = event_data.get('transit_secret')
    if transit_secret is not None and not transit_secret:
        return False

    return True