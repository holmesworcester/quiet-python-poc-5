"""
Tests for event_crypto handler.
"""
import pytest
from protocols.quiet.handlers.event_crypto import (
    filter_func, handler, unseal_key_event, decrypt_event, encrypt_event
)
from protocols.quiet.tests.handlers.test_base import HandlerTestBase


class TestEventCryptoHandler(HandlerTestBase):
    """Test the event_crypto handler."""
    
    def test_filter_accepts_decrypt_case(self):
        """Test filter accepts envelopes needing decryption/unsealing."""
        envelope = self.create_envelope(
            deps_included_and_valid=True,
            should_remove=False,
            key_ref={"kind": "peer", "id": "test_peer"}
        )
        assert filter_func(envelope) is True
    
    def test_filter_rejects_decrypt_with_plaintext(self):
        """Test filter rejects decrypt if plaintext already present."""
        envelope = self.create_envelope(
            deps_included_and_valid=True,
            should_remove=False,
            key_ref={"kind": "peer", "id": "test_peer"},
            event_plaintext={"already": "decrypted"}
        )
        assert filter_func(envelope) is False
    
    def test_filter_accepts_encrypt_case(self):
        """Test filter accepts validated plaintext for encryption."""
        envelope = self.create_envelope(
            validated=True,
            event_plaintext={"type": "message", "content": "test"}
        )
        assert filter_func(envelope) is True
    
    def test_filter_rejects_encrypt_with_ciphertext(self):
        """Test filter rejects if already encrypted."""
        envelope = self.create_envelope(
            validated=True,
            event_plaintext={"type": "message"},
            event_ciphertext=b"already_encrypted"
        )
        assert filter_func(envelope) is False
    
    def test_handler_routes_to_unseal_for_peer(self):
        """Test handler routes to unseal for peer key_ref."""
        envelope = self.create_envelope(
            key_ref={"kind": "peer", "id": "test_peer"},
            event_ciphertext=b"sealed_data",
            resolved_deps={
                "identity:test_peer": {
                    "event_plaintext": {"peer_id": "test_peer"},
                    "local_metadata": {"private_key": "test_key"}
                }
            }
        )
        
        result = handler(envelope)
        
        # Should have unsealed key event fields
        assert result['event_type'] == 'key'
        assert 'key_id' in result
        assert 'unsealed_secret' in result
        assert 'group_id' in result
        assert 'prekey_id' in result
        assert 'tag_id' in result
        assert result['write_to_store'] is True
        assert result['sig_checked'] is True  # Bypass signature
        assert result['validated'] is True
    
    def test_handler_routes_to_decrypt_for_key(self):
        """Test handler routes to decrypt for key key_ref."""
        envelope = self.create_envelope(
            key_ref={"kind": "key", "id": "group_key_123"},
            event_ciphertext=b"encrypted_data",
            resolved_deps={
                "key:group_key_123": {
                    "unsealed_secret": b"group_secret"
                }
            }
        )
        
        result = handler(envelope)
        
        # Should have decrypted event
        assert 'event_plaintext' in result
        assert result['write_to_store'] is True
    
    def test_handler_rejects_invalid_key_ref(self):
        """Test handler rejects invalid key_ref."""
        # Not a dict
        envelope = self.create_envelope(
            key_ref="invalid"
        )
        result = handler(envelope)
        assert 'error' in result
        
        # Missing kind
        envelope = self.create_envelope(
            key_ref={"id": "test"}
        )
        result = handler(envelope)
        assert 'error' in result
        
        # Invalid kind
        envelope = self.create_envelope(
            key_ref={"kind": "invalid", "id": "test"}
        )
        result = handler(envelope)
        assert 'error' in result
    
    def test_encrypt_sets_key_ref_for_group(self):
        """Test encrypt sets key_ref for group messages."""
        envelope = self.create_envelope(
            event_plaintext={
                "type": "message",
                "group_id": "test_group",
                "content": "Hello"
            },
            event_id="already_set_by_signature",
            peer_id="sender"
        )
        
        result = encrypt_event(envelope)
        
        assert 'event_ciphertext' in result
        assert 'key_ref' in result
        assert result['key_ref']['kind'] == 'key'
        assert result['key_ref']['id'] == 'group_key_test_group'
        assert result['write_to_store'] is True
    
    def test_encrypt_sets_key_ref_for_direct(self):
        """Test encrypt sets key_ref for direct messages."""
        envelope = self.create_envelope(
            event_plaintext={
                "type": "message",
                "peer_id": "recipient",
                "content": "Hello"
            },
            event_id="already_set_by_signature"
        )
        
        result = encrypt_event(envelope)
        
        assert 'event_ciphertext' in result
        assert 'key_ref' in result
        assert result['key_ref']['kind'] == 'peer'
        assert result['key_ref']['id'] == 'recipient'
    
    def test_encrypt_requires_event_id(self):
        """Test encrypt requires event_id from signature handler."""
        envelope = self.create_envelope(
            event_plaintext={"type": "test"}
            # Missing event_id
        )
        
        result = encrypt_event(envelope)
        
        assert 'error' in result
        assert 'event_id' in result['error']
    
    def test_decrypt_extracts_event_type(self):
        """Test decrypt extracts event_type from plaintext."""
        envelope = self.create_envelope(
            key_ref={"kind": "key", "id": "test_key"},
            event_ciphertext=b"encrypted",
            resolved_deps={}
        )
        
        result = decrypt_event(envelope)
        
        # Stub implementation would set type
        assert 'event_plaintext' in result
        if 'type' in result['event_plaintext']:
            assert result['event_type'] == result['event_plaintext']['type']
    
    def test_unseal_includes_kem_fields(self):
        """Test unseal includes KEM-specific fields."""
        envelope = self.create_envelope(
            key_ref={"kind": "peer", "id": "test_peer"},
            event_ciphertext=b"sealed"
        )
        
        result = unseal_key_event(envelope)
        
        # KEM-specific fields
        assert 'prekey_id' in result
        assert 'tag_id' in result
        
        # Key event fields
        assert result['event_type'] == 'key'
        assert 'key_id' in result
        assert 'unsealed_secret' in result
        assert 'group_id' in result