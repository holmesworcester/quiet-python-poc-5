"""
Signature handler - Handles both signing and verification of events.

From plan.md:
- Sign Filter: `self_created: true` AND `deps_included_and_valid: true` AND no signature
- Verify Filter: `event_plaintext` exists AND `sig_checked` is not true AND `deps_included_and_valid: true`
- Transform: Signs events or verifies signatures
"""
from typing import Any, List
import sqlite3
import json
import hashlib
from core.handlers import Handler


def canonicalize_event(event_plaintext: dict) -> bytes:
    """
    Create canonical 512-byte representation of signed event.
    
    The protocol requires a specific 512-byte format for event IDs.
    This is a stub implementation - the real one would:
    1. Serialize to deterministic JSON
    2. Pad or truncate to exactly 512 bytes
    3. Follow the protocol's specific canonical format
    """
    # TODO: Implement proper canonical serialization
    # For now, create a deterministic JSON representation
    canonical_json = json.dumps(event_plaintext, sort_keys=True, separators=(',', ':'))
    canonical_bytes = canonical_json.encode('utf-8')
    
    # Pad or truncate to 512 bytes (this is a stub - real protocol has specific format)
    if len(canonical_bytes) > 512:
        return canonical_bytes[:512]
    else:
        return canonical_bytes.ljust(512, b'\0')


def filter_func(envelope: dict[str, Any]) -> bool:
    """
    Process envelopes that need signing or signature verification.
    Key events (unsealed, not signed) and identity events (local-only) are skipped.
    """
    # Skip key events - they are sealed, not signed
    if envelope.get('event_type') == 'key':
        return False

    # Skip identity events - they are local-only and don't need signing
    if envelope.get('event_type') == 'identity':
        return False

    # Skip if already has a signature error
    if envelope.get('sig_failed') or envelope.get('error'):
        return False

    # Sign case: self-created events that need signing
    if (envelope.get('self_created') is True and
        envelope.get('deps_included_and_valid') is True and
        'event_plaintext' in envelope):
        event_plaintext = envelope['event_plaintext']
        if not event_plaintext.get('signature'):
            return True

    # Verify case: events with plaintext that need sig checking
    if ('event_plaintext' in envelope and
        envelope.get('sig_checked') is not True and
        envelope.get('deps_included_and_valid') is True):
        return True

    return False


def handler(envelope: dict[str, Any], db: sqlite3.Connection) -> dict[str, Any]:
    """
    Handle signing and signature verification.

    Args:
        envelope: dict[str, Any] needing signature operations
        db: Database connection for core identity access

    Returns:
        dict[str, Any] with signature added or sig_checked status
    """
    event_plaintext = envelope.get('event_plaintext', {})

    # Determine operation
    if envelope.get('self_created') and not event_plaintext.get('signature'):
        # Sign the event using core identity
        return sign_event(envelope, db)
    else:
        # Verify signature
        return verify_signature(envelope)


def sign_event(envelope: dict[str, Any], db: sqlite3.Connection) -> dict[str, Any]:
    """Sign a self-created event using the identity associated with the peer."""
    from core.identity import sign_with_identity

    event_plaintext = envelope.get('event_plaintext', {})
    event_type = envelope.get('event_type')

    # Determine which public key to use for signing
    public_key_hex = None

    if event_type == 'peer':
        # For peer events, use the public_key from the event itself
        public_key_hex = event_plaintext.get('public_key')
        if not public_key_hex:
            envelope['error'] = "Peer event missing public_key"
            envelope['sig_failed'] = True
            return envelope
    else:
        # For other events, look up the peer's public key
        peer_id = envelope.get('peer_id')
        if not peer_id:
            envelope['error'] = "No peer_id in envelope for signing"
            envelope['sig_failed'] = True
            return envelope

        # Handle placeholder peer_ids (for events created in batches)
        if peer_id.startswith('@generated:'):
            # Can't sign yet - will be signed later when peer_id is resolved
            envelope['sig_deferred'] = True
            return envelope

        # Look up peer's public key from database
        cursor = db.execute("""
            SELECT public_key FROM peers
            WHERE peer_id = ?
        """, (peer_id,))
        row = cursor.fetchone()

        if not row:
            envelope['error'] = f"Peer {peer_id} not found in database"
            envelope['sig_failed'] = True
            return envelope

        public_key_hex = row[0]
        if isinstance(public_key_hex, bytes):
            public_key_hex = public_key_hex.hex()

    # Sign with the identity that has this public key
    event_copy = event_plaintext.copy()
    event_copy.pop('signature', None)
    canonical = canonicalize_event(event_copy)

    try:
        signature = sign_with_identity(public_key_hex, canonical, db)
    except ValueError as e:
        envelope['error'] = str(e)
        envelope['sig_failed'] = True
        return envelope

    envelope['event_plaintext']['signature'] = signature
    envelope['sig_checked'] = True
    envelope['self_signed'] = True

    return envelope


def verify_signature(envelope: dict[str, Any]) -> dict[str, Any]:
    """Verify signature on an event."""
    from core import crypto

    event_plaintext = envelope.get('event_plaintext', {})
    signature = event_plaintext.get('signature')

    if not signature:
        envelope['error'] = "No signature in event"
        envelope['sig_checked'] = False
        return envelope

    # Get public key from peer dependency if available
    peer_id = event_plaintext.get('peer_id')
    public_key = None

    if peer_id and envelope.get('resolved_deps'):
        # Try to get public key from resolved peer dependency
        peer_dep = envelope['resolved_deps'].get(f'peer:{peer_id}')
        if peer_dep and peer_dep.get('event_plaintext'):
            public_key = peer_dep['event_plaintext'].get('public_key')

    # Fallback to public key in event (for self-attested or legacy events)
    if not public_key:
        public_key = event_plaintext.get('public_key')

    if not public_key:
        envelope['error'] = "No public_key available for verification"
        envelope['sig_checked'] = False
        return envelope

    # Create canonical form without signature
    event_to_verify = event_plaintext.copy()
    event_to_verify.pop('signature', None)

    # Verify signature
    try:
        canonical = canonicalize_event(event_to_verify)
        sig_bytes = bytes.fromhex(signature)
        pub_key_bytes = bytes.fromhex(public_key)

        if crypto.verify(canonical, sig_bytes, pub_key_bytes):
            envelope['sig_checked'] = True
        else:
            envelope['error'] = "Signature verification failed"
            envelope['sig_checked'] = False
            envelope['sig_failed'] = True
    except Exception as e:
        envelope['error'] = f"Signature verification error: {str(e)}"
        envelope['sig_checked'] = False
        envelope['sig_failed'] = True

    # Extract peer_id from event if it's a peer event
    if event_plaintext.get('type') == 'peer':
        envelope['peer_id'] = envelope.get('event_id')  # peer_id IS the event_id for peer events

    # Note: event_id should already be present from crypto handler (generated from ciphertext)
    # If not present, it means this event came through an unusual path
    if 'event_id' not in envelope:
        envelope['error'] = "No event_id found - should be set by crypto handler from ciphertext"

    return envelope

class SignatureHandler(Handler):
    """Handler that signs self-created events and verifies signatures."""

    @property
    def name(self) -> str:
        return "signature"

    def filter(self, envelope: dict[str, Any]) -> bool:
        """Process envelopes that need signing or signature verification."""
        return filter_func(envelope)

    def process(self, envelope: dict[str, Any], db: sqlite3.Connection) -> List[dict[str, Any]]:
        """Sign or verify signature on envelope."""
        result = handler(envelope, db)
        # Always emit the envelope so pipeline can continue
        # Downstream handlers can check sig_failed flag if they care
        if result:
            return [result]
        return []
