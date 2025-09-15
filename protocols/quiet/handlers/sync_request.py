"""Handler for processing sync requests and generating responses."""

import sqlite3
from typing import List, Dict, Any
from core.handlers import Handler
from protocols.quiet.events.sync_request.commands import (
    create_sync_response,
    fetch_network_events,
    store_transit_secret,
    get_transit_secret
)


# In-memory cache for transit secrets
# In production, this could be a proper cache or DB table
TRANSIT_SECRET_CACHE = {}


class SyncRequestHandler(Handler):
    """
    Processes incoming sync requests and generates sync responses.

    Sync requests are ephemeral - they trigger immediate action but
    are not stored in the database.
    """

    @property
    def name(self) -> str:
        return "sync_request"

    def filter(self, envelope: Dict[str, Any]) -> bool:
        """
        Process incoming sync requests.
        """
        # Process incoming sync requests (after being unsealed)
        if (envelope.get('is_sync_request') and
            envelope.get('event_plaintext') and
            not envelope.get('is_outgoing')):
            return True

        # Also store transit secrets for outgoing sync requests
        if (envelope.get('event_type') == 'sync_request' and
            envelope.get('is_outgoing') and
            envelope.get('event_plaintext')):
            return True

        return False

    def process(self, envelope: Dict[str, Any], db: sqlite3.Connection) -> List[Dict[str, Any]]:
        """
        Process sync request and generate responses.
        """
        event_plaintext = envelope.get('event_plaintext', {})

        # Handle outgoing sync request - store transit secret
        if envelope.get('is_outgoing'):
            request_id = event_plaintext.get('request_id')
            transit_secret = event_plaintext.get('transit_secret')

            if request_id and transit_secret:
                store_transit_secret(TRANSIT_SECRET_CACHE, request_id, transit_secret)
                print(f"Stored transit secret for sync request {request_id}")

            # Outgoing requests continue through pipeline for sending
            return [envelope]

        # Handle incoming sync request - generate responses
        if event_plaintext.get('type') == 'sync_request':
            return self._handle_incoming_sync_request(event_plaintext, db)

        return []

    def _handle_incoming_sync_request(self, request: Dict[str, Any],
                                     db: sqlite3.Connection) -> List[Dict[str, Any]]:
        """
        Handle an incoming sync request by sending back our events.

        Args:
            request: The sync request event
            db: Database connection

        Returns:
            List of response envelopes
        """
        network_id = request.get('network_id')
        if not network_id:
            print("Sync request missing network_id")
            return []

        print(f"Processing sync request for network {network_id}")

        # Fetch events for this network
        # TODO: In real implementation, track what we've already sent
        # to avoid resending the same events repeatedly
        events = fetch_network_events(db, network_id, limit=100)

        if not events:
            print(f"No events to sync for network {network_id}")
            return []

        print(f"Sending {len(events)} events in response to sync request")

        # Create response envelopes
        responses = create_sync_response(request, events)

        return responses


class SyncResponseHandler(Handler):
    """
    Processes sync responses (events sent in response to our sync requests).

    Handles deduplication and validation of responses.
    """

    @property
    def name(self) -> str:
        return "sync_response"

    def filter(self, envelope: Dict[str, Any]) -> bool:
        """
        Process envelopes that are responses to sync requests.
        """
        # Look for in_response_to field
        return 'in_response_to' in envelope and not envelope.get('is_outgoing')

    def process(self, envelope: Dict[str, Any], db: sqlite3.Connection) -> List[Dict[str, Any]]:
        """
        Process sync response - validate and deduplicate.
        """
        request_id = envelope.get('in_response_to')
        if not request_id:
            return []

        # Validate transit secret if we have one
        transit_secret = get_transit_secret(TRANSIT_SECRET_CACHE, request_id)
        if not transit_secret:
            print(f"Warning: No transit secret found for request {request_id}")
            # Could still process if we trust the sender

        # Check for duplicate event
        event_id = envelope.get('event_id')
        if event_id and self._is_duplicate(db, event_id):
            print(f"Skipping duplicate event {event_id}")
            return []

        # Event is new - allow it to continue through pipeline
        print(f"Processing new event {event_id} from sync response")

        # Remove response marker so it processes normally
        del envelope['in_response_to']

        return [envelope]

    def _is_duplicate(self, db: sqlite3.Connection, event_id: str) -> bool:
        """
        Check if an event already exists in the database.

        Args:
            db: Database connection
            event_id: Event ID to check

        Returns:
            True if event exists, False otherwise
        """
        cursor = db.cursor()
        result = cursor.execute(
            "SELECT 1 FROM events WHERE event_id = ? LIMIT 1",
            (event_id,)
        ).fetchone()

        return result is not None