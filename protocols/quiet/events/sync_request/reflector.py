"""Reflector for sync request - reflects sync requests with events."""

import sqlite3
from typing import Dict, List, Any, Tuple


def sync_request_reflector(envelope: Dict, db: sqlite3.Connection, time_now_ms: int) -> Tuple[bool, List[Dict]]:
    """
    Simple sync response reflector - reflects sync requests with events.

    When an identity receives a sync_request, it sends back events from that network.
    """
    try:
        # Don't reflect to sync_request events that are already responses
        if envelope.get('in_response_to'):
            print("[sync_request_reflector] Ignoring sync_request that is already a response")
            return True, []

        request = envelope.get('event_plaintext', {})
        network_id = request.get('network_id')
        request_id = request.get('request_id')
        from_identity = request.get('from_identity')  # Who sent this request
        to_peer = request.get('to_peer')  # Which of our identities received it
        last_sync_ms = request.get('last_sync_ms', 0)

        if not network_id:
            print("[sync_request_reflector] No network_id in sync request")
            return False, []

        if not from_identity:
            print("[sync_request_reflector] No from_identity in sync request")
            return False, []

        # Check if we have the identity that was requested as a user in this network
        cursor = db.cursor()
        identity_exists = cursor.execute("""
            SELECT 1 FROM users
            WHERE user_id = ? AND network_id = ?
        """, (to_peer, network_id)).fetchone()

        if not identity_exists:
            print(f"[sync_request_reflector] Identity {to_peer} not found in network {network_id}")
            return True, []  # Not an error, just not for us

        # Get events for this network since last sync
        # In a real system, we'd filter by what the requester is allowed to see
        # IMPORTANT: Exclude sync_request events to prevent loops
        events = cursor.execute("""
            SELECT event_id, event_type, event_ciphertext
            FROM events
            WHERE network_id = ? AND created_ms > ? AND event_type != 'sync_request'
            ORDER BY created_ms ASC
            LIMIT 100
        """, (network_id, last_sync_ms)).fetchall()

        if not events:
            print(f"[sync_request_reflector] No new events for network {network_id} since {last_sync_ms}")
            return True, []

        # Create response envelopes
        response_envelopes = []
        for event_id, event_type, event_ciphertext in events:
            response = {
                'event_id': event_id,
                'event_type': event_type,
                'event_ciphertext': event_ciphertext,
                'peer_id': to_peer,  # Which identity is sending this response
                'seal_to': from_identity,  # Send back to requester
                'is_outgoing': True,
                'network_id': network_id,
                'in_response_to': request_id
            }
            response_envelopes.append(response)

        print(f"[sync_request_reflector] Identity {to_peer} sending {len(response_envelopes)} events to {from_identity}")
        return True, response_envelopes

    except Exception as e:
        print(f"[sync_request_reflector] Error: {e}")
        return False, []