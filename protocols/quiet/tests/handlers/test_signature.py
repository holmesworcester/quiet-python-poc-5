"""
Tests for signature handler.
"""
import pytest
from protocols.quiet.handlers.signature import (
    filter_func, handler, sign_event, verify_signature, canonicalize_event
)
from .test_base import HandlerTestBase


class TestSignatureHandler(HandlerTestBase):
    """Test the signature handler."""
    
    def test_filter_skips_key_events(self):
        """Test filter skips key events (sealed, not signed)."""
        envelope = self.create_envelope(
            event_type="key",
            event_plaintext={"type": "key"},
            deps_included_and_valid=True
        )
        assert filter_func(envelope) is False
    
    def test_filter_accepts_self_created_unsigned(self):
        """Test filter accepts self-created events needing signature."""
        envelope = self.create_envelope(
            self_created=True,
            deps_included_and_valid=True,
            event_plaintext={"type": "message", "content": "test"}
        )
        assert filter_func(envelope) is True
    
    def test_filter_rejects_self_created_signed(self):
        """Test filter rejects already signed self-created events."""
        envelope = self.create_envelope(
            self_created=True,
            deps_included_and_valid=True,
            event_plaintext={"type": "message", "signature": "already_signed"}
        )
        assert filter_func(envelope) is False
    
    def test_filter_accepts_incoming_unsigned(self):
        """Test filter accepts incoming events needing verification."""
        envelope = self.create_envelope(
            event_plaintext={"type": "message", "signature": "sig"},
            deps_included_and_valid=True
        )
        assert filter_func(envelope) is True
    
    def test_filter_rejects_already_verified(self):
        """Test filter rejects already verified events."""
        envelope = self.create_envelope(
            event_plaintext={"type": "message", "signature": "sig"},
            sig_checked=True,
            deps_included_and_valid=True
        )
        assert filter_func(envelope) is False
    
    def test_handler_routes_to_sign(self):
        """Test handler routes to sign_event for self-created."""
        envelope = self.create_envelope(
            self_created=True,
            deps_included_and_valid=True,
            event_plaintext={
                "type": "message",
                "peer_id": "test_peer_id",
                "content": "test"
            },
            resolved_deps={
                "identity:test_peer_id": {
                    "event_plaintext": {"peer_id": "test_peer_id"},
                    "local_metadata": {"private_key": "test_private_key"}
                }
            }
        )
        
        result = handler(envelope)
        
        # Should have signature and event_id
        assert 'signature' in result['event_plaintext']
        assert result['sig_checked'] is True
        assert result['self_signed'] is True
        assert 'event_id' in result
    
    def test_handler_routes_to_verify(self):
        """Test handler routes to verify_signature for incoming."""
        envelope = self.create_envelope(
            event_plaintext={
                "type": "message",
                "peer_id": "sender",
                "signature": "test_sig",
                "content": "test"
            },
            deps_included_and_valid=True,
            resolved_deps={
                "peer:sender": {
                    "event_plaintext": {"peer_id": "sender", "public_key": "pub_key"}
                }
            }
        )
        
        result = handler(envelope)
        
        # Should be verified with event_id
        assert result['sig_checked'] is True
        assert result['peer_id'] == 'sender'
        assert 'event_id' in result
    
    def test_sign_requires_peer_id(self):
        """Test sign requires peer_id."""
        envelope = self.create_envelope(
            event_plaintext={"type": "message"}  # Missing peer_id
        )
        
        result = sign_event(envelope)
        
        assert 'error' in result
        assert 'peer_id' in result['error']
    
    def test_sign_uses_resolved_identity(self):
        """Test sign uses identity from resolved_deps."""
        envelope = self.create_envelope(
            peer_id="test_peer",
            event_plaintext={
                "type": "message",
                "peer_id": "test_peer",
                "content": "test"
            },
            resolved_deps={
                "identity:test_peer": {
                    "local_metadata": {"private_key": "secret_key"}
                }
            }
        )
        
        result = sign_event(envelope)
        
        # Should have used the private key to sign
        assert 'signature' in result['event_plaintext']
        assert result['self_signed'] is True
        assert 'event_id' in result
    
    def test_verify_requires_signature(self):
        """Test verify requires signature in plaintext."""
        envelope = self.create_envelope(
            event_plaintext={"type": "message", "peer_id": "sender"}
            # Missing signature
        )
        
        result = verify_signature(envelope)
        
        assert 'error' in result
        assert result['sig_checked'] is False
    
    def test_verify_requires_peer_id(self):
        """Test verify requires peer_id in plaintext."""
        envelope = self.create_envelope(
            event_plaintext={"type": "message", "signature": "sig"}
            # Missing peer_id
        )
        
        result = verify_signature(envelope)
        
        assert 'error' in result
        assert result['sig_checked'] is False
    
    def test_verify_sets_envelope_peer_id(self):
        """Test verify sets peer_id at envelope level."""
        envelope = self.create_envelope(
            event_plaintext={
                "type": "message",
                "peer_id": "sender",
                "signature": "sig"
            },
            resolved_deps={}
        )
        
        result = verify_signature(envelope)
        
        assert result['peer_id'] == 'sender'
        assert result['sig_checked'] is True
        assert 'event_id' in result
    
    def test_canonicalize_event_pads_to_512(self):
        """Test canonicalize pads small events to 512 bytes."""
        event = {"type": "test", "small": True}
        
        canonical = canonicalize_event(event)
        
        assert len(canonical) == 512
        assert canonical.endswith(b'\0' * (512 - len(canonical.rstrip(b'\0'))))
    
    def test_canonicalize_event_truncates_large(self):
        """Test canonicalize truncates large events to 512 bytes."""
        event = {"type": "test", "data": "x" * 1000}
        
        canonical = canonicalize_event(event)
        
        assert len(canonical) == 512
    
    def test_canonicalize_deterministic(self):
        """Test canonicalize produces deterministic output."""
        event = {"b": 2, "a": 1, "c": {"y": 2, "x": 1}}
        
        canonical1 = canonicalize_event(event)
        canonical2 = canonicalize_event(event)
        
        assert canonical1 == canonical2