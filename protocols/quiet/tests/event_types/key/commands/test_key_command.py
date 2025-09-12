"""
Tests for key event type command (create).
"""
import pytest
import sys
import json
from pathlib import Path

# Add project root to path
test_dir = Path(__file__).parent
protocol_dir = test_dir.parent.parent.parent.parent.parent
project_root = protocol_dir.parent.parent
sys.path.insert(0, str(project_root))

from protocols.quiet.event_types.key.commands.create import create_key
from protocols.quiet.event_types.identity.commands.create import create_identity
from core.crypto import verify, unseal


class TestKeyCommand:
    """Test key creation command."""
    
    @pytest.fixture
    def identity_in_db(self, initialized_db):
        """Create an identity in the database for testing."""
        # Create identity
        params = {"network_id": "test-network"}
        envelopes = create_identity(params, initialized_db)
        identity_id = envelopes[0]["event_plaintext"]["peer_id"]
        
        return {
            "identity_id": identity_id,
            "network_id": "test-network"
        }
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_key_basic(self, initialized_db, identity_in_db):
        """Test basic key creation."""
        params = {
            "group_id": "test-group",
            "network_id": identity_in_db["network_id"],
            "identity_id": identity_in_db["identity_id"]
        }
        
        envelopes = create_key(params, initialized_db)
        
        # Should emit exactly one envelope
        assert len(envelopes) == 1
        
        envelope = envelopes[0]
        assert "event_plaintext" in envelope
        assert "event_type" in envelope
        assert envelope["event_type"] == "key"
        assert envelope["self_created"] == True
        
        # Check event content
        event = envelope["event_plaintext"]
        assert event["type"] == "key"
        assert event["group_id"] == "test-group"
        assert event["network_id"] == "test-network"
        assert event["peer_id"] == identity_in_db["identity_id"]
        assert "key_id" in event
        assert "sealed_secret" in event
        assert "created_at" in event
        assert "signature" in event
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_key_missing_group_id(self, initialized_db, identity_in_db):
        """Test that missing group_id raises error."""
        params = {
            "network_id": identity_in_db["network_id"],
            "identity_id": identity_in_db["identity_id"]
        }
        
        with pytest.raises(ValueError, match="group_id is required"):
            create_key(params, initialized_db)
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_key_missing_network_id(self, initialized_db, identity_in_db):
        """Test that missing network_id raises error."""
        params = {
            "group_id": "test-group",
            "identity_id": identity_in_db["identity_id"]
        }
        
        with pytest.raises(ValueError, match="network_id is required"):
            create_key(params, initialized_db)
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_key_missing_identity_id(self, initialized_db):
        """Test that missing identity_id raises error."""
        params = {
            "group_id": "test-group",
            "network_id": "test-network"
        }
        
        with pytest.raises(ValueError, match="identity_id is required"):
            create_key(params, initialized_db)
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_key_invalid_identity(self, initialized_db):
        """Test that invalid identity_id raises error."""
        params = {
            "group_id": "test-group",
            "network_id": "test-network",
            "identity_id": "non-existent-identity"
        }
        
        with pytest.raises(ValueError, match="Identity .* not found"):
            create_key(params, initialized_db)
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_key_signature_valid(self, initialized_db, identity_in_db):
        """Test that the created key has a valid signature."""
        params = {
            "group_id": "test-group",
            "network_id": identity_in_db["network_id"],
            "identity_id": identity_in_db["identity_id"]
        }
        
        envelopes = create_key(params, initialized_db)
        event = envelopes[0]["event_plaintext"]
        
        # Remove signature from event for verification
        signature_hex = event["signature"]
        signature = bytes.fromhex(signature_hex)
        
        # Create the message that was signed
        event_copy = event.copy()
        del event_copy["signature"]
        message = json.dumps(event_copy, sort_keys=True).encode()
        
        # Get public key
        public_key = bytes.fromhex(event["peer_id"])
        
        # Verify signature
        assert verify(message, signature, public_key)
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_key_sealed_secret(self, initialized_db, identity_in_db):
        """Test that sealed secret is properly formatted."""
        params = {
            "group_id": "test-group",
            "network_id": identity_in_db["network_id"],
            "identity_id": identity_in_db["identity_id"]
        }
        
        envelopes = create_key(params, initialized_db)
        event = envelopes[0]["event_plaintext"]
        
        # Check sealed_secret is hex
        sealed_secret_hex = event["sealed_secret"]
        assert len(sealed_secret_hex) > 0
        bytes.fromhex(sealed_secret_hex)  # Should not raise
        
        # The sealed secret should be decodable with the private key
        # (though we can't test that here without access to private key)
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_key_deterministic_key_id(self, initialized_db, identity_in_db):
        """Test that key_id is deterministic based on event content."""
        params = {
            "group_id": "test-group",
            "network_id": identity_in_db["network_id"],
            "identity_id": identity_in_db["identity_id"]
        }
        
        # Create two keys for same group
        envelopes1 = create_key(params, initialized_db)
        envelopes2 = create_key(params, initialized_db)
        
        key_id1 = envelopes1[0]["event_plaintext"]["key_id"]
        key_id2 = envelopes2[0]["event_plaintext"]["key_id"]
        
        # Key IDs should be different (different timestamps and secrets)
        assert key_id1 != key_id2
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_multiple_keys_same_group(self, initialized_db, identity_in_db):
        """Test creating multiple keys for the same group."""
        params = {
            "group_id": "test-group",
            "network_id": identity_in_db["network_id"],
            "identity_id": identity_in_db["identity_id"]
        }
        
        # Create three keys for same group
        key_ids = []
        for i in range(3):
            envelopes = create_key(params, initialized_db)
            key_id = envelopes[0]["event_plaintext"]["key_id"]
            key_ids.append(key_id)
        
        # All key IDs should be unique
        assert len(set(key_ids)) == 3
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_key_envelope_structure(self, initialized_db, identity_in_db):
        """Test that the envelope has correct structure for pipeline processing."""
        params = {
            "group_id": "test-group",
            "network_id": identity_in_db["network_id"],
            "identity_id": identity_in_db["identity_id"]
        }
        
        envelopes = create_key(params, initialized_db)
        envelope = envelopes[0]
        
        # Required fields for pipeline
        assert envelope["event_type"] == "key"
        assert envelope["self_created"] == True
        assert envelope["peer_id"] == identity_in_db["identity_id"]
        assert envelope["network_id"] == identity_in_db["network_id"]