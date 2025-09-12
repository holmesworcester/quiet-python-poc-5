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

from protocols.quiet.handlers.check_sig.handler import CheckSigHandler
from core.crypto import sign, generate_keypair


class TestCheckSigHandler:
    """Test signature checking handler."""
    
    @pytest.fixture
    def handler(self):
        """Create handler instance."""
        return CheckSigHandler()
    
    @pytest.mark.unit
    @pytest.mark.handler
    def test_filter_no_sig_checked(self, handler):
        """Test filter matches envelopes without sig_checked."""
        envelope = {
            "event_type": "identity",
            "event_plaintext": {"type": "identity"},
            "deps_included_and_valid": True
        }
        assert handler.filter(envelope) == True
        
        envelope_with_false = {
            "event_type": "identity",
            "event_plaintext": {"type": "identity"},
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
    def test_process_valid_signature(self, handler, sample_identity_event, initialized_db):
        """Test processing event with valid signature."""
        envelope = {
            "event_plaintext": sample_identity_event,
            "event_type": "identity",
            "peer_id": sample_identity_event["peer_id"],
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
    def test_process_invalid_signature(self, handler, sample_identity_event, initialized_db):
        """Test processing event with invalid signature."""
        # Corrupt the signature
        event = sample_identity_event.copy()
        event["signature"] = "0" * 128  # Invalid signature
        
        envelope = {
            "event_plaintext": event,
            "event_type": "identity",
            "peer_id": event["peer_id"],
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
    def test_process_tampered_event(self, handler, sample_identity_event, initialized_db):
        """Test processing event where content was tampered."""
        # Change content after signing
        event = sample_identity_event.copy()
        event["network_id"] = "tampered-network"
        
        envelope = {
            "event_plaintext": event,
            "event_type": "identity",
            "peer_id": event["peer_id"],
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
    def test_process_missing_signature(self, handler, sample_identity_event, initialized_db):
        """Test processing event without signature."""
        event = sample_identity_event.copy()
        del event["signature"]
        
        envelope = {
            "event_plaintext": event,
            "event_type": "identity",
            "peer_id": event["peer_id"],
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
            "type": "identity",
            "peer_id": "a" * 64,  # Different peer_id
            "network_id": "test-network",
            "created_at": 1000
        }
        
        # But sign with our test identity's key
        message = json.dumps(event, sort_keys=True).encode()
        signature = sign(message, test_identity["private_key"])
        event["signature"] = signature.hex()
        
        envelope = {
            "event_plaintext": event,
            "event_type": "identity",
            "peer_id": event["peer_id"],
            "deps_included_and_valid": True
        }
        
        results = handler.process(envelope, initialized_db)
        
        assert len(results) == 1
        result = results[0]
        
        # Should fail - signature doesn't match claimed peer_id
        assert result["sig_checked"] == True
        assert "error" in result