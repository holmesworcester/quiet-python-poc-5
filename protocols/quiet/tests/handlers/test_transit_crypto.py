"""
Tests for transit_crypto handler.
"""
import pytest
from protocols.quiet.handlers.transit_crypto import filter_func, handler, decrypt_transit, encrypt_transit
from .test_base import HandlerTestBase


class TestTransitCryptoHandler(HandlerTestBase):
    """Test the transit_crypto handler."""
    
    def test_filter_accepts_decrypt_case(self):
        """Test filter accepts envelopes needing transit decryption."""
        envelope = self.create_envelope(
            deps_included_and_valid=True,
            transit_key_id="test_key",
            transit_ciphertext=b"encrypted_data"
        )
        assert filter_func(envelope) is True
    
    def test_filter_rejects_decrypt_with_key_ref(self):
        """Test filter rejects decrypt if key_ref already present."""
        envelope = self.create_envelope(
            deps_included_and_valid=True,
            transit_key_id="test_key",
            transit_ciphertext=b"encrypted_data",
            key_ref={"kind": "peer", "id": "test_peer"}
        )
        assert filter_func(envelope) is False
    
    def test_filter_accepts_encrypt_case(self):
        """Test filter accepts envelopes needing transit encryption."""
        envelope = self.create_envelope(
            outgoing_checked=True,
            event_ciphertext=b"event_encrypted",
            transit_key_id="test_key"
        )
        assert filter_func(envelope) is True
    
    def test_handler_routes_to_decrypt(self):
        """Test handler routes to decrypt_transit when appropriate."""
        envelope = self.create_envelope(
            deps_included_and_valid=True,
            transit_key_id="test_transit_key",
            transit_ciphertext=b"encrypted_data",
            resolved_deps={
                "transit_key:test_transit_key": {
                    "transit_secret": b"test_transit_secret",
                    "network_id": "test_network"
                }
            }
        )
        
        result = handler(envelope)
        
        # Should have decrypted and extracted event layer
        assert 'network_id' in result
        assert 'event_ciphertext' in result
        assert 'key_ref' in result
        assert result['write_to_store'] is True
    
    def test_handler_routes_to_encrypt(self):
        """Test handler routes to encrypt_transit when appropriate."""
        envelope = self.create_envelope(
            outgoing_checked=True,
            event_ciphertext=b"event_data",
            transit_key_id="test_transit_key",
            key_ref={"kind": "key", "id": "group_key_123"},
            network_id="test_network",
            resolved_deps={
                "transit_key:test_transit_key": {
                    "transit_secret": b"test_transit_secret",
                    "network_id": "test_network"
                }
            }
        )
        
        result = handler(envelope)
        
        # Should only have transit layer data
        assert 'transit_ciphertext' in result
        assert 'transit_key_id' in result
        assert 'dest_ip' in result
        assert 'dest_port' in result
        assert 'event_ciphertext' not in result  # Stripped
        assert 'key_ref' not in result  # Stripped
    
    def test_decrypt_preserves_network_metadata(self):
        """Test decrypt preserves received_at and origin info."""
        envelope = self.create_envelope(
            transit_key_id="test_transit_key",
            transit_ciphertext=b"encrypted",
            received_at=1234567890,
            origin_ip="192.168.1.1",
            origin_port=8080,
            resolved_deps={
                "transit_key:test_transit_key": {
                    "transit_secret": b"secret",
                    "network_id": "test"
                }
            }
        )
        
        result = decrypt_transit(envelope)
        
        assert result['received_at'] == 1234567890
        assert result['origin_ip'] == "192.168.1.1"
        assert result['origin_port'] == 8080
    
    def test_decrypt_extracts_key_ref(self):
        """Test decrypt extracts key_ref from transit data."""
        envelope = self.create_envelope(
            transit_key_id="test_transit_key",
            transit_ciphertext=b"encrypted",
            peer_id="test_peer",  # Hints at peer encryption
            resolved_deps={
                "transit_key:test_transit_key": {
                    "transit_secret": b"secret",
                    "network_id": "test"
                }
            }
        )
        
        result = decrypt_transit(envelope)
        
        assert 'key_ref' in result
        assert result['key_ref']['kind'] == 'peer'
        assert result['key_ref']['id'] == 'test_peer'
    
    def test_encrypt_creates_minimal_envelope(self):
        """Test encrypt creates envelope with only transit data."""
        envelope = self.create_envelope(
            event_ciphertext=b"event_data",
            transit_key_id="test_transit_key",
            key_ref={"kind": "key", "id": "key_123"},
            network_id="test_network",
            event_id="should_be_stripped",
            event_plaintext={"should": "be_stripped"},
            resolved_deps={
                "transit_key:test_transit_key": {
                    "transit_secret": b"secret",
                    "network_id": "test"
                }
            },
            dest_ip="10.0.0.1",
            dest_port=9999,
            due_ms=5000
        )
        
        result = encrypt_transit(envelope)
        
        # Should only have transit layer fields
        assert 'transit_ciphertext' in result
        assert 'transit_key_id' in result
        assert result['dest_ip'] == "10.0.0.1"
        assert result['dest_port'] == 9999
        assert result['due_ms'] == 5000
        
        # Should strip sensitive data
        assert 'event_ciphertext' not in result
        assert 'key_ref' not in result
        assert 'event_id' not in result
        assert 'event_plaintext' not in result
        assert 'network_id' not in result