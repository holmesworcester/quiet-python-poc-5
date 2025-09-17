"""
Protocol-level reflectors mapping.

Map event_type -> callable(envelope, db, time_now_ms) -> (success, envelopes)
"""

from protocols.quiet.events.sync_request.reflector import sync_request_reflector

REFLECTORS = {
    'sync_request': sync_request_reflector,
}

