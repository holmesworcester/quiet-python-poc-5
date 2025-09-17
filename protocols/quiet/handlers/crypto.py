"""
Unified Crypto handler - Handles both transit and event encryption/decryption.

This is a PURE handler that:
- Uses only resolved_deps for key material (no database access)
- Only processes envelopes with deps_included_and_valid=true (ignores envelopes with missing deps)
- Transforms envelopes without side effects

Replaces the legacy transit_crypto and event_crypto handlers.
SQL schemas (transit_keys, event_keys tables) are deprecated - all keys come from events.
"""
from typing import Any, List
import sqlite3
import hashlib
from core.handlers import Handler


def filter_func(envelope: dict[str, Any]) -> bool:
    """
    Process envelopes that need any crypto operations.
    """
    # Transit decrypt: incoming with transit encryption
    if (envelope.get('deps_included_and_valid') is True and
        'transit_key_id' in envelope and
        'transit_ciphertext' in envelope and
        'key_ref' not in envelope):
        return True

    # Transit encrypt: outgoing that needs transit encryption
    if (envelope.get('outgoing_checked') is True and
        'event_ciphertext' in envelope and
        'transit_key_id' in envelope):
        return True

    # Event decrypt/unseal: has key_ref but no plaintext
    if (envelope.get('deps_included_and_valid') is True and
        envelope.get('should_remove') is False and
        'key_ref' in envelope and
        'event_plaintext' not in envelope):
        return True

    # Event encrypt: validated plaintext that needs encryption
    # Include identity events for ID generation but not encryption
    if (envelope.get('validated') is True and
        'event_plaintext' in envelope and
        'event_ciphertext' not in envelope):
        return True

    # Seal case: has seal_to field and plaintext
    if ('seal_to' in envelope and
        'event_plaintext' in envelope and
        'event_sealed' not in envelope):
        return True

    # Open sealed case: has event_sealed but no plaintext
    if ('event_sealed' in envelope and
        'event_plaintext' not in envelope):
        return True

    return False


def handler(envelope: dict[str, Any]) -> dict[str, Any]:
    """
    Handle all crypto operations in order:
    1. Transit decryption (if incoming)
    2. Event decryption/unsealing (if encrypted)
    3. Event encryption/sealing (if outgoing)
    4. Transit encryption (if outgoing)

    Args:
        envelope: dict[str, Any] needing crypto operations

    Returns:
        Transformed envelope
    """
    # Phase 1: Transit decryption (incoming)
    if ('transit_ciphertext' in envelope and
        'key_ref' not in envelope and
        envelope.get('deps_included_and_valid')):
        envelope = decrypt_transit(envelope)

    # Phase 2: Event-layer operations
    # Handle seal/unseal first (special case of event crypto)
    if 'seal_to' in envelope and 'event_plaintext' in envelope:
        envelope = seal_event(envelope)
    elif 'event_sealed' in envelope and 'event_plaintext' not in envelope:
        envelope = open_sealed_event(envelope)
    # Then handle regular event crypto
    elif 'key_ref' in envelope and 'event_plaintext' not in envelope:
        # Decrypt or unseal based on key_ref type
        key_ref = envelope['key_ref']
        if isinstance(key_ref, dict) and key_ref.get('kind') == 'peer':
            # Key event - unseal using KEM to peer/prekey
            envelope = unseal_key_event(envelope)
        elif isinstance(key_ref, dict) and key_ref.get('kind') == 'key':
            # Regular event - decrypt using symmetric key
            envelope = decrypt_event(envelope)
        else:
            envelope['error'] = f"Invalid key_ref: {key_ref}"
    elif envelope.get('validated') and 'event_plaintext' in envelope and 'event_ciphertext' not in envelope:
        # Encrypt validated event
        envelope = encrypt_event(envelope)

    # Phase 3: Transit encryption (outgoing)
    if (envelope.get('outgoing_checked') and
        'event_ciphertext' in envelope and
        'transit_key_id' in envelope):
        return encrypt_transit(envelope)

    return envelope


def decrypt_transit(envelope: dict[str, Any]) -> dict[str, Any]:
    """Decrypt transit layer to reveal event encryption layer."""
    # TODO: Implement actual decryption logic

    # Extract transit key from resolved_deps
    transit_key_id = envelope['transit_key_id']
    resolved_deps = envelope.get('resolved_deps', {})

    # transit_key_id can be identity, peer, or key
    transit_key_data = None
    network_id = None

    # Try different dependency types
    if f"identity:{transit_key_id}" in resolved_deps:
        transit_key_data = resolved_deps[f"identity:{transit_key_id}"]
        network_id = transit_key_data.get('event_plaintext', {}).get('network_id')
    elif f"peer:{transit_key_id}" in resolved_deps:
        transit_key_data = resolved_deps[f"peer:{transit_key_id}"]
        network_id = transit_key_data.get('event_plaintext', {}).get('network_id')
    elif f"key:{transit_key_id}" in resolved_deps:
        transit_key_data = resolved_deps[f"key:{transit_key_id}"]
        network_id = transit_key_data.get('network_id')
    else:
        # Fallback to old transit_key dependency format
        transit_key_dep = f"transit_key:{transit_key_id}"
        transit_key_data = resolved_deps.get(transit_key_dep, {})
        network_id = transit_key_data.get('network_id', 'stub_network_id')

    # Would normally:
    # 1. Decrypt transit_ciphertext using transit key
    # 2. Extract network_id, key_ref, event_ciphertext
    # 3. Parse key_ref to determine encryption type

    # Stub implementation
    envelope['network_id'] = network_id
    envelope['event_ciphertext'] = b'stub_event_ciphertext'

    # Generate event_id from the event ciphertext (not transit ciphertext)
    # This allows deduplication and dependency tracking before event decryption
    h = hashlib.blake2b(envelope['event_ciphertext'], digest_size=16)
    envelope['event_id'] = h.hexdigest()

    # Extract key_ref from decrypted transit data
    # This would normally come from the decrypted transit plaintext
    # For stub, determine based on context
    if envelope.get('peer_id'):
        # Peer-encrypted event (e.g., key event sealed to peer)
        envelope['key_ref'] = {
            'kind': 'peer',
            'id': envelope['peer_id']
        }
    else:
        # Group/network encrypted event
        envelope['key_ref'] = {
            'kind': 'key',
            'id': 'stub_key_event_id'
        }

    # Note: event_id will be generated by signature_handler after decryption
    # and signature verification from the canonical signed plaintext
    envelope['write_to_store'] = True

    # Preserve network metadata
    for field in ['received_at', 'origin_ip', 'origin_port']:
        if field in envelope:
            envelope[field] = envelope[field]

    return envelope


def encrypt_transit(envelope: dict[str, Any]) -> dict[str, Any]:
    """Apply transit layer encryption to outgoing envelope."""
    # TODO: Implement actual transit encryption logic

    # Extract transit key from resolved_deps
    transit_key_id = envelope['transit_key_id']
    resolved_deps = envelope.get('resolved_deps', {})

    # Try different dependency types for transit key
    transit_key_data = None
    if f"identity:{transit_key_id}" in resolved_deps:
        transit_key_data = resolved_deps[f"identity:{transit_key_id}"]
    elif f"peer:{transit_key_id}" in resolved_deps:
        transit_key_data = resolved_deps[f"peer:{transit_key_id}"]
    elif f"key:{transit_key_id}" in resolved_deps:
        transit_key_data = resolved_deps[f"key:{transit_key_id}"]
    else:
        # Fallback to old format
        transit_key_dep = f"transit_key:{transit_key_id}"
        transit_key_data = resolved_deps.get(transit_key_dep, {})

    # Would normally:
    # 1. Create transit plaintext containing event_ciphertext and metadata
    # 2. Encrypt using transit key
    # 3. Strip all sensitive data from envelope

    # Stub: Wrap event ciphertext in transit "encryption"
    event_ciphertext = envelope['event_ciphertext']
    transit_plaintext = {
        'event_ciphertext': event_ciphertext,
        'key_ref': envelope.get('key_ref'),
        'network_id': envelope.get('network_id')
    }

    # Create new envelope with only transit-layer data
    transit_envelope: dict[str, Any] = {
        'transit_ciphertext': f"transit_encrypted:{transit_plaintext}".encode(),
        'transit_key_id': transit_key_id,
        'dest_ip': envelope.get('dest_ip', '127.0.0.1'),
        'dest_port': envelope.get('dest_port', 8080),
        'due_ms': envelope.get('due_ms', 0)
    }

    return transit_envelope


def unseal_key_event(envelope: dict[str, Any]) -> dict[str, Any]:
    """Unseal a key event using peer's identity and KEM."""
    # TODO: Implement actual KEM unsealing logic

    # Would normally:
    # 1. Get identity from resolved_deps
    # 2. Get prekey private key from local storage
    # 3. Use crypto_box_seal_open with prekey to unseal
    # 4. Extract key_id, unsealed_secret, group_id

    # Key events use KEM (crypto_box_seal) to prekeys
    envelope['event_type'] = 'key'
    envelope['key_id'] = f"key_{envelope.get('event_key_id', 'stub')}"  # Stub
    envelope['unsealed_secret'] = b'stub_unsealed_secret'  # Stub
    envelope['group_id'] = 'stub_group_id'  # Stub
    envelope['prekey_id'] = 'stub_prekey_id'  # Which prekey was used
    envelope['tag_id'] = 'stub_tag_id'  # KEM tag
    envelope['write_to_store'] = True

    # Key events bypass signature verification
    envelope['sig_checked'] = True  # Mark as checked to skip sig handler
    envelope['validated'] = True    # Key events are self-validating after unsealing

    return envelope


def decrypt_event(envelope: dict[str, Any]) -> dict[str, Any]:
    """Decrypt a regular event."""
    # TODO: Implement actual decryption logic

    # Would normally:
    # 1. Get key from resolved_deps using event_key_id
    # 2. Decrypt event_ciphertext using the key
    # 3. Parse decrypted data as event_plaintext

    # Stub implementation
    envelope['event_plaintext'] = {
        'type': envelope.get('event_type', 'unknown'),
        'content': 'stub_decrypted_content'
    }

    # Extract event_type from plaintext if not already set
    if 'event_type' not in envelope and 'type' in envelope['event_plaintext']:
        envelope['event_type'] = envelope['event_plaintext']['type']

    # Note: event_id is generated by signature_handler from canonical signed plaintext
    # It should already be present in the envelope

    envelope['write_to_store'] = True

    return envelope


def encrypt_event(envelope: dict[str, Any]) -> dict[str, Any]:
    """Encrypt a validated plaintext event."""

    event_plaintext = envelope.get('event_plaintext', {})
    event_type = envelope.get('event_type')

    # Identity events: compute deterministic ID only (no encryption)
    if event_type == 'identity':
        # Use the identity_id from plaintext as the event_id
        # This keeps identity references consistent across the system.
        identity_id = event_plaintext.get('identity_id')
        if not identity_id:
            # Fallback: derive from public_key if necessary
            pub = event_plaintext.get('public_key', '')
            try:
                pb = bytes.fromhex(pub)
                h = hashlib.blake2b(pb, digest_size=16)
                identity_id = h.hexdigest()
            except Exception:
                identity_id = ''
        envelope['event_id'] = identity_id
        # Do not set event_ciphertext or key_ref for identity
        # Leave write_to_store untouched (projector will handle storage)
        return envelope

    # Regular event encryption
    # TODO: Implement actual encryption logic
    # Would normally:
    # 1. Determine which key to use for encryption (from network/group context)
    # 2. Serialize event_plaintext to canonical 512-byte form
    # 3. Encrypt the serialized data
    # 4. Set key_ref to indicate which key was used

    # Stub: Use a deterministic "encryption" for testing
    plaintext_str = str(event_plaintext)
    envelope['event_ciphertext'] = f"encrypted:{plaintext_str}".encode()

    # Determine key_ref (would normally come from group/network context)
    if 'group_id' in event_plaintext:
        # Group events use symmetric key encryption
        envelope['key_ref'] = {
            'kind': 'key',
            'id': f"group_key_{event_plaintext['group_id']}"
        }
    else:
        # Network events might use peer encryption
        peer_id = event_plaintext.get('peer_id', envelope.get('peer_id', 'default_peer'))
        envelope['key_ref'] = {
            'kind': 'peer',
            'id': peer_id
        }

    # Generate event_id from ciphertext (blake2b-16 hash)
    # This ensures consistent event_id across all nodes
    h = hashlib.blake2b(envelope['event_ciphertext'], digest_size=16)
    envelope['event_id'] = h.hexdigest()

    envelope['write_to_store'] = True

    return envelope


def seal_event(envelope: dict[str, Any]) -> dict[str, Any]:
    """
    Seal an event to a peer's public key (one-way encryption).

    Used for sync requests where the sender can't decrypt their own message.
    """
    from core.crypto import seal
    import json

    seal_to = envelope.get('seal_to')  # Peer ID to seal to
    event_plaintext = envelope.get('event_plaintext')

    if not seal_to or not event_plaintext:
        envelope['error'] = "seal_to and event_plaintext required for sealing"
        return envelope

    # TODO: Get peer's public key from database
    # For now, stub implementation
    peer_public_key = b'stub_public_key_for_' + seal_to.encode()[:32].ljust(32, b'\0')

    # Serialize plaintext
    plaintext_bytes = json.dumps(event_plaintext).encode('utf-8')

    # Seal to peer's public key
    try:
        # In real implementation, would use actual seal function
        # envelope['event_sealed'] = seal(plaintext_bytes, peer_public_key)
        envelope['event_sealed'] = b'sealed:' + plaintext_bytes  # Stub

        # Remove plaintext after sealing
        del envelope['event_plaintext']

        # Mark for outgoing if specified
        if envelope.get('is_outgoing'):
            envelope['write_to_store'] = False  # Don't store outgoing sync requests

    except Exception as e:
        envelope['error'] = f"Failed to seal: {e}"

    return envelope


def open_sealed_event(envelope: dict[str, Any]) -> dict[str, Any]:
    """
    Open a sealed event using our private key.

    Used for receiving sync requests sealed to our public key.
    """
    from core.crypto import unseal
    import json

    event_sealed = envelope.get('event_sealed')
    if not event_sealed:
        envelope['error'] = "event_sealed required for opening"
        return envelope

    # TODO: Get our private key from database
    # For now, stub implementation
    our_private_key = b'stub_private_key'.ljust(32, b'\0')
    our_public_key = b'stub_public_key'.ljust(32, b'\0')

    try:
        # In real implementation, would use actual unseal function
        # plaintext_bytes = unseal(event_sealed, our_private_key, our_public_key)

        # Stub: just remove prefix
        if event_sealed.startswith(b'sealed:'):
            plaintext_bytes = event_sealed[7:]
        else:
            plaintext_bytes = event_sealed

        # Parse plaintext
        event_plaintext = json.loads(plaintext_bytes.decode('utf-8'))
        envelope['event_plaintext'] = event_plaintext

        # Sync requests are not stored
        if event_plaintext.get('type') == 'sync_request':
            envelope['write_to_store'] = False
            envelope['is_sync_request'] = True

    except Exception as e:
        envelope['error'] = f"Failed to open sealed: {e}"

    return envelope


class CryptoHandler(Handler):
    """Unified handler for all crypto operations."""

    @property
    def name(self) -> str:
        return "crypto"

    def filter(self, envelope: dict[str, Any]) -> bool:
        """Check if this handler should process the envelope."""
        return filter_func(envelope)

    def process(self, envelope: dict[str, Any], db: sqlite3.Connection) -> List[dict[str, Any]]:
        """Process the envelope."""
        result = handler(envelope)
        if result:
            return [result]
        return []
