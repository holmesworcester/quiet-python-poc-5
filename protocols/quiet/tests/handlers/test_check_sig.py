"""
Tests for check_sig handler.
"""
import pytest
import sys
import json
from pathlib import Path

# Add project root to path
protocol_dir = Path(__file__).parent.parent.parent
project_root = protocol_dir.parent.parent
sys.path.insert(0, str(project_root))

from protocols.quiet.handlers.signature import SignatureHandler
from core.crypto import sign, generate_keypair


class TestCheckSigHandler:
    """Test signature checking handler."""
    
    @pytest.fixture
    def handler(self):
        """Create handler instance."""
        return SignatureHandler()
    
    @pytest.mark.unit
    @pytest.mark.handler
    def test_filter_no_sig_checked(self, handler):
        """Test filter matches envelopes without sig_checked."""
        envelope = {
            "event_type": "peer",
            "event_plaintext": {"type": "peer", "public_key": "ab"*32, "identity_id": "id"},
            "deps_included_and_valid": True
        }
        assert handler.filter(envelope) == True
        
        envelope_with_false = {
            "event_type": "peer",
            "event_plaintext": {"type": "peer", "public_key": "cd"*32, "identity_id": "id2"},
            "deps_included_and_valid": True,
            "sig_checked": False
        }
        assert handler.filter(envelope_with_false) == True
    
    @pytest.mark.unit
    @pytest.mark.handler
    def test_filter_already_checked(self, handler):
        """Test filter rejects envelopes with sig already checked."""
        envelope = {
            "event_type": "identity",
            "event_plaintext": {"type": "identity"},
            "deps_included_and_valid": True,
            "sig_checked": True
        }
        assert handler.filter(envelope) == False
    
    @pytest.mark.unit
    @pytest.mark.handler
    def test_filter_requires_deps_valid(self, handler):
        """Test filter requires deps_included_and_valid."""
        envelope = {
            "event_type": "identity",
            "event_plaintext": {"type": "identity"},
            "deps_included_and_valid": False
        }
        assert handler.filter(envelope) == False
    
    @pytest.mark.unit
    @pytest.mark.handler
    def test_process_valid_signature(self, handler, test_identity, initialized_db):
        """Test processing event with valid signature."""
        import json
        event = {
            "type": "peer",
            "public_key": test_identity["public_key"].hex(),
            "identity_id": "core-id-1",
            "username": "User",
            "created_at": 1000
        }
        message = json.dumps(event, sort_keys=True).encode()
        signature = sign(message, test_identity["private_key"]).hex()
        event["signature"] = signature
        envelope = {
            "event_plaintext": event,
            "event_type": "peer",
            "deps_included_and_valid": True
        }
        
        results = handler.process(envelope, initialized_db)
        
        assert len(results) == 1
        result = results[0]
        
        # Should mark signature as checked and valid
        assert result["sig_checked"] == True
        assert "error" not in result
    
    @pytest.mark.unit
    @pytest.mark.handler
    def test_process_invalid_signature(self, handler, test_identity, initialized_db):
        """Test processing event with invalid signature."""
        import json
        event = {
            "type": "peer",
            "public_key": test_identity["public_key"].hex(),
            "identity_id": "core-id-1",
            "username": "User",
            "created_at": 1000,
            "signature": "0" * 128
        }
        
        envelope = {
            "event_plaintext": event,
            "event_type": "peer",
            "deps_included_and_valid": True
        }
        
        results = handler.process(envelope, initialized_db)
        
        assert len(results) == 1
        result = results[0]
        
        # Should mark signature as checked but with error
        assert result["sig_checked"] == True
        assert "error" in result
        assert "signature" in result["error"].lower()
    
    @pytest.mark.unit
    @pytest.mark.handler
    def test_process_tampered_event(self, handler, test_identity, initialized_db):
        """Test processing event where content was tampered."""
        import json
        base = {
            "type": "peer",
            "public_key": test_identity["public_key"].hex(),
            "identity_id": "core-id-1",
            "username": "User",
            "created_at": 1000
        }
        message = json.dumps(base, sort_keys=True).encode()
        sig = sign(message, test_identity["private_key"]).hex()
        tampered = base.copy()
        tampered["username"] = "Hacked"
        tampered["signature"] = sig
        
        envelope = {
            "event_plaintext": tampered,
            "event_type": "peer",
            "deps_included_and_valid": True
        }
        
        results = handler.process(envelope, initialized_db)
        
        assert len(results) == 1
        result = results[0]
        
        # Should fail signature check
        assert result["sig_checked"] == True
        assert "error" in result
    
    @pytest.mark.unit
    @pytest.mark.handler
    def test_process_missing_signature(self, handler, test_identity, initialized_db):
        """Test processing event without signature."""
        event = {
            "type": "peer",
            "public_key": test_identity["public_key"].hex(),
            "identity_id": "core-id-1",
            "username": "User",
            "created_at": 1000
        }
        
        envelope = {
            "event_plaintext": event,
            "event_type": "peer",
            "deps_included_and_valid": True
        }
        
        results = handler.process(envelope, initialized_db)
        
        assert len(results) == 1
        result = results[0]
        
        # Should mark as checked with error
        assert result["sig_checked"] == True
        assert "error" in result
        assert "missing" in result["error"].lower() or "signature" in result["error"].lower()
    
    @pytest.mark.unit
    @pytest.mark.handler
    def test_process_different_signer(self, handler, test_identity, initialized_db):
        """Test event signed by different key than peer_id claims."""
        # Create event claiming to be from one peer
        event = {
            "type": "peer",
            "public_key": ("b"*64),  # Different key than signer
            "identity_id": "core-id-1",
            "username": "User",
            "created_at": 1000
        }
        
        # But sign with our test identity's key
        message = json.dumps(event, sort_keys=True).encode()
        signature = sign(message, test_identity["private_key"])
        event["signature"] = signature.hex()
        
        envelope = {
            "event_plaintext": event,
            "event_type": "peer",
            "deps_included_and_valid": True
        }
        
        results = handler.process(envelope, initialized_db)
        
        assert len(results) == 1
        result = results[0]
        
        # Should fail - signature doesn't match claimed peer_id
        assert result["sig_checked"] == True
        assert "error" in result
