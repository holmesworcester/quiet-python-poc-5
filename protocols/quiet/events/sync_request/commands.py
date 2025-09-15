"""Commands for sync request events."""

import time
import uuid
import secrets
from typing import Dict, Any, List, Optional
from core.core_types import command
import sqlite3


@command
def create_sync_request(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a sync request to probe a peer for updates.

    This is typically called by a job every few seconds.

    Args:
        params: Parameters including:
            - network_id: Network to sync
            - peer_id: Our peer ID
            - user_id: Our user ID
            - target_peer_id: Peer to sync with (optional)

    Returns:
        Envelope with sync request
    """
    network_id = params.get('network_id', '')
    peer_id = params.get('peer_id', '')
    user_id = params.get('user_id', '')
    target_peer_id = params.get('target_peer_id', '')

    if not network_id or not peer_id:
        raise ValueError("network_id and peer_id are required")

    # Generate unique request ID and transit secret
    request_id = str(uuid.uuid4())
    transit_secret = secrets.token_hex(16)

    # Create sync request event
    event = {
        'type': 'sync_request',
        'request_id': request_id,
        'network_id': network_id,
        'peer_id': peer_id,
        'user_id': user_id,
        'transit_secret': transit_secret,
        'timestamp_ms': int(time.time() * 1000),
        'target_peer_id': target_peer_id
    }

    # Create envelope
    envelope = {
        'event_type': 'sync_request',
        'event_plaintext': event,
        'is_outgoing': True,  # Mark for sending
        'network_id': network_id,
        'peer_id': peer_id,
        'deps': []  # No dependencies for sync requests
    }

    # If we have a specific target, seal to them
    if target_peer_id:
        envelope['seal_to'] = target_peer_id

    return envelope


def create_sync_response(request: Dict[str, Any], events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Create sync response envelopes for a sync request.

    Args:
        request: The incoming sync request
        events: List of events to send back

    Returns:
        List of response envelopes
    """
    request_id = request.get('request_id', '')
    requester_peer_id = request.get('peer_id', '')

    if not request_id or not requester_peer_id:
        return []

    responses = []
    for event in events:
        # Wrap each event as a response
        response_envelope = {
            'event_id': event.get('event_id', ''),
            'event_type': event.get('event_type', ''),
            'event_ciphertext': event.get('event_ciphertext'),
            'event_plaintext': event.get('event_plaintext'),
            'seal_to': requester_peer_id,  # Seal to requester
            'is_outgoing': True,
            'in_response_to': request_id,  # Mark as response
            'network_id': request.get('network_id', '')
        }
        responses.append(response_envelope)

    return responses


def fetch_network_events(db: sqlite3.Connection, network_id: str,
                         since_event_id: Optional[str] = None,
                         limit: int = 1000) -> List[Dict[str, Any]]:
    """
    Fetch events for a network from the database.

    Args:
        db: Database connection
        network_id: Network ID to fetch events for
        since_event_id: Only fetch events after this ID (for incremental sync)
        limit: Maximum number of events to return

    Returns:
        List of event dictionaries
    """
    cursor = db.cursor()

    # Base query to fetch events
    query = """
        SELECT event_id, event_type, event_ciphertext, event_plaintext, timestamp_ms
        FROM events
        WHERE network_id = ?
    """
    params = [network_id]

    # Add incremental sync if requested
    if since_event_id:
        query += " AND event_id > ?"
        params.append(since_event_id)

    # Order by event ID for consistent ordering
    query += " ORDER BY event_id ASC LIMIT ?"
    params.append(limit)

    results = cursor.execute(query, params).fetchall()

    events = []
    for row in results:
        event = {
            'event_id': row[0],
            'event_type': row[1],
            'event_ciphertext': row[2],
            'event_plaintext': row[3],
            'timestamp_ms': row[4]
        }
        events.append(event)

    return events


def store_transit_secret(cache: Dict[str, Any], request_id: str, secret: str,
                        ttl_ms: int = 30000) -> None:
    """
    Store a transit secret for correlating responses.

    Args:
        cache: In-memory cache (or could be a DB table)
        request_id: Request ID
        secret: Transit secret
        ttl_ms: Time to live in milliseconds
    """
    expire_at = int(time.time() * 1000) + ttl_ms
    cache[request_id] = {
        'secret': secret,
        'expire_at': expire_at
    }


def get_transit_secret(cache: Dict[str, Any], request_id: str) -> Optional[str]:
    """
    Retrieve a transit secret if not expired.

    Args:
        cache: In-memory cache
        request_id: Request ID

    Returns:
        Transit secret or None if not found/expired
    """
    if request_id not in cache:
        return None

    entry = cache[request_id]
    current_time = int(time.time() * 1000)

    if current_time > entry['expire_at']:
        # Expired
        del cache[request_id]
        return None

    return entry['secret']


def cleanup_expired_secrets(cache: Dict[str, Any]) -> int:
    """
    Remove expired transit secrets from cache.

    Args:
        cache: In-memory cache

    Returns:
        Number of secrets removed
    """
    current_time = int(time.time() * 1000)
    expired_keys = []

    for request_id, entry in cache.items():
        if current_time > entry['expire_at']:
            expired_keys.append(request_id)

    for key in expired_keys:
        del cache[key]

    return len(expired_keys)