"""
Signature handler - Handles both signing and verification of events.

From plan.md:
- Sign Filter: `self_created: true` AND `deps_included_and_valid: true` AND no signature
- Verify Filter: `event_plaintext` exists AND `sig_checked` is not true AND `deps_included_and_valid: true`
- Transform: Signs events or verifies signatures
"""

from core.types import Envelope
import hashlib
import json


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


def filter_func(envelope: Envelope) -> bool:
    """
    Process envelopes that need signing or signature verification.
    Key events (unsealed, not signed) are skipped.
    """
    # Skip key events - they are sealed, not signed
    if envelope.get('event_type') == 'key':
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


def handler(envelope: Envelope) -> Envelope:
    """
    Handle signing and signature verification.
    
    Args:
        envelope: Envelope needing signature operations
        
    Returns:
        Envelope with signature added or sig_checked status
    """
    event_plaintext = envelope.get('event_plaintext', {})
    
    # Determine operation
    if envelope.get('self_created') and not event_plaintext.get('signature'):
        # Sign the event
        return sign_event(envelope)
    else:
        # Verify signature
        return verify_signature(envelope)


def sign_event(envelope: Envelope) -> Envelope:
    """Sign a self-created event."""
    # TODO: Implement actual signing logic
    
    # Get identity from resolved_deps
    peer_id = envelope.get('peer_id') or envelope['event_plaintext'].get('peer_id')
    if not peer_id:
        envelope['error'] = "No peer_id for signing"
        return envelope
    
    identity_dep = f"identity:{peer_id}"
    resolved_deps = envelope.get('resolved_deps', {})
    identity_data = resolved_deps.get(identity_dep, {})
    
    # Would normally:
    # 1. Get private key from identity's local_metadata
    # 2. Create canonical JSON of event_plaintext without signature
    # 3. Sign the canonical form
    # 4. Add signature to event_plaintext
    
    # Stub implementation
    private_key = identity_data.get('local_metadata', {}).get('private_key', 'stub_private_key')
    
    # Add signature to event_plaintext
    envelope['event_plaintext']['signature'] = f"stub_signature_by_{peer_id}"
    envelope['sig_checked'] = True
    envelope['self_signed'] = True
    
    # Generate event_id from canonical signed plaintext (512 bytes)
    # This MUST happen after signing but before encryption
    canonical_signed_plaintext = canonicalize_event(envelope['event_plaintext'])
    h = hashlib.blake2b(canonical_signed_plaintext, digest_size=16)
    envelope['event_id'] = h.hexdigest()
    
    return envelope


def verify_signature(envelope: Envelope) -> Envelope:
    """Verify signature on an event."""
    # TODO: Implement actual verification logic
    
    event_plaintext = envelope.get('event_plaintext', {})
    signature = event_plaintext.get('signature')
    peer_id = event_plaintext.get('peer_id')
    
    if not signature:
        envelope['error'] = "No signature in event"
        envelope['sig_checked'] = False
        return envelope
    
    if not peer_id:
        envelope['error'] = "No peer_id in event"
        envelope['sig_checked'] = False
        return envelope
    
    # Get peer's public key from resolved_deps
    peer_dep = f"peer:{peer_id}"
    resolved_deps = envelope.get('resolved_deps', {})
    peer_data = resolved_deps.get(peer_dep, {})
    
    # Would normally:
    # 1. Get public key from peer identity event
    # 2. Create canonical JSON of event_plaintext without signature
    # 3. Verify signature matches
    
    # Stub: Always pass for now
    envelope['sig_checked'] = True
    
    # Set peer_id at envelope level for downstream handlers
    envelope['peer_id'] = peer_id
    
    # Generate event_id from canonical signed plaintext
    # This happens after signature verification for incoming events
    canonical_signed_plaintext = canonicalize_event(event_plaintext)
    h = hashlib.blake2b(canonical_signed_plaintext, digest_size=16)
    envelope['event_id'] = h.hexdigest()
    
    return envelope