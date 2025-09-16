"""
Tests for key event type command (create).
"""
import pytest
import sys
import json
from pathlib import Path

# Add project root to path
test_dir = Path(__file__).parent
protocol_dir = test_dir.parent.parent.parent.parent
project_root = protocol_dir.parent.parent
sys.path.insert(0, str(project_root))

from protocols.quiet.events.key.commands import create_key
from core.identity import create_identity
from core.crypto import verify, unseal


class TestKeyCommand:
    """Test key creation command."""
    
    @pytest.fixture
    def identity_in_db(self, initialized_db):
        """Create an identity in the database for testing."""
        # Create identity in the initialized test database
        db_path = initialized_db.execute("PRAGMA database_list").fetchone()[2]
        identity = create_identity("Test User", db_path)
        identity_id = identity.id
        
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
        
        envelope = create_key(params)
        
        # Should emit exactly one envelope
        # Single envelope returned

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
        assert event["key_id"] == ""  # Empty until handlers process
        assert "sealed_secret" in event
        assert "created_at" in event
        assert event["signature"] == ""  # Empty until handlers process
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_key_missing_group_id(self, initialized_db, identity_in_db):
        """Test that missing group_id uses empty string default."""
        params = {
            "network_id": identity_in_db["network_id"],
            "identity_id": identity_in_db["identity_id"]
        }

        envelope = create_key(params)
        assert envelope["event_plaintext"]["group_id"] == ""
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_key_missing_network_id(self, initialized_db, identity_in_db):
        """Test that missing network_id uses empty string default."""
        params = {
            "group_id": "test-group",
            "identity_id": identity_in_db["identity_id"]
        }

        envelope = create_key(params)
        assert envelope["event_plaintext"]["network_id"] == ""
        assert envelope["network_id"] == ""
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_key_missing_identity_id(self, initialized_db):
        """Test that missing identity_id uses empty string default."""
        params = {
            "group_id": "test-group",
            "network_id": "test-network"
        }

        envelope = create_key(params)
        assert envelope["event_plaintext"]["peer_id"] == ""
        assert envelope["peer_id"] == ""
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_key_with_any_identity_id(self, initialized_db):
        """Test that any identity_id works (no validation in commands)."""
        params = {
            "group_id": "test-group",
            "network_id": "test-network",
            "identity_id": "non-existent-identity"
        }

        envelope = create_key(params)
        assert envelope["event_plaintext"]["peer_id"] == "non-existent-identity"
        assert envelope["peer_id"] == "non-existent-identity"
    
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_key_sealed_secret(self, initialized_db, identity_in_db):
        """Test that sealed secret is properly formatted."""
        params = {
            "group_id": "test-group",
            "network_id": identity_in_db["network_id"],
            "identity_id": identity_in_db["identity_id"]
        }
        
        envelope = create_key(params)
        event = envelope["event_plaintext"]
        
        # Check sealed_secret is hex
        sealed_secret_hex = event["sealed_secret"]
        assert len(sealed_secret_hex) > 0
        bytes.fromhex(sealed_secret_hex)  # Should not raise
        
        # The sealed secret should be decodable with the private key
        # (though we can't test that here without access to private key)
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_key_empty_key_id(self, initialized_db, identity_in_db):
        """Test that key_id is empty until processed by handlers."""
        params = {
            "group_id": "test-group",
            "network_id": identity_in_db["network_id"],
            "identity_id": identity_in_db["identity_id"]
        }

        # Create two keys for same group
        envelope1 = create_key(params)
        envelope2 = create_key(params)

        key_id1 = envelope1["event_plaintext"]["key_id"]
        key_id2 = envelope2["event_plaintext"]["key_id"]

        # Key IDs should both be empty strings until handlers process them
        assert key_id1 == ""
        assert key_id2 == ""
    
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
            envelope = create_key(params)
            key_id = envelope["event_plaintext"]["key_id"]
            key_ids.append(key_id)

        # All key IDs should be empty strings until handlers process them
        assert all(key_id == "" for key_id in key_ids)
        assert len(key_ids) == 3
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_key_envelope_structure(self, initialized_db, identity_in_db):
        """Test that the envelope has correct structure for pipeline processing."""
        params = {
            "group_id": "test-group",
            "network_id": identity_in_db["network_id"],
            "identity_id": identity_in_db["identity_id"]
        }
        
        envelope = create_key(params)

        # Required fields for pipeline
        assert envelope["event_type"] == "key"
        assert envelope["self_created"] == True
        assert envelope["peer_id"] == identity_in_db["identity_id"]
        assert envelope["network_id"] == identity_in_db["network_id"]
