"""
Tests for transit_secret event type command (create).
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

from protocols.quiet.events.transit_secret.commands import create_transit_secret
from core.identity import create_identity
from core.crypto import verify


class TestTransitSecretCommand:
    """Test transit secret creation command."""
    
    @pytest.fixture
    def identity_in_db(self, initialized_db):
        """Create an identity in the database for testing."""
        # Create identity
        params = {"network_id": "test-network"}
        envelope = create_identity(params)
        identity_id = envelope["event_plaintext"]["peer_id"]
        
        return {
            "identity_id": identity_id,
            "network_id": "test-network"
        }
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_transit_secret_basic(self, initialized_db, identity_in_db):
        """Test basic transit secret creation."""
        params = {
            "network_id": identity_in_db["network_id"],
            "identity_id": identity_in_db["identity_id"]
        }
        
        envelope = create_transit_secret(params)
        
        # Should emit exactly one envelope
        # Single envelope returned
        
        assert "event_plaintext" in envelope
        assert "event_type" in envelope
        assert envelope["event_type"] == "transit_secret"
        assert envelope["self_created"] == True
        
        # Check event content
        event = envelope["event_plaintext"]
        assert event["type"] == "transit_secret"
        assert event["network_id"] == "test-network"
        assert event["peer_id"] == identity_in_db["identity_id"]
        assert event["transit_key_id"] == ""  # Empty until handlers process
        assert "created_at" in event
        assert event["signature"] == ""  # Empty until handlers process
        
        # Should NOT contain the actual secret
        assert "secret" not in event
        assert "encrypted_secret" not in event
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_transit_secret_missing_network_id(self, initialized_db, identity_in_db):
        """Test that missing network_id uses empty string default."""
        params = {
            "identity_id": identity_in_db["identity_id"]
        }

        envelope = create_transit_secret(params)
        assert envelope["event_plaintext"]["network_id"] == ""
        assert envelope["network_id"] == ""
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_transit_secret_missing_identity_id(self, initialized_db):
        """Test that missing identity_id uses empty string default."""
        params = {
            "network_id": "test-network"
        }

        envelope = create_transit_secret(params)
        assert envelope["event_plaintext"]["peer_id"] == ""
        assert envelope["peer_id"] == ""
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_transit_secret_with_any_identity_id(self, initialized_db):
        """Test that any identity_id works (no validation in commands)."""
        params = {
            "network_id": "test-network",
            "identity_id": "non-existent-identity"
        }

        envelope = create_transit_secret(params)
        assert envelope["event_plaintext"]["peer_id"] == "non-existent-identity"
        assert envelope["peer_id"] == "non-existent-identity"
    
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_transit_secret_empty_key_ids(self, initialized_db, identity_in_db):
        """Test that transit_key_id is empty until processed by handlers."""
        params = {
            "network_id": identity_in_db["network_id"],
            "identity_id": identity_in_db["identity_id"]
        }

        # Create three transit secrets
        key_ids = []
        for i in range(3):
            envelope = create_transit_secret(params)
            key_id = envelope["event_plaintext"]["transit_key_id"]
            key_ids.append(key_id)

        # All key IDs should be empty strings until handlers process them
        assert all(key_id == "" for key_id in key_ids)
        assert len(key_ids) == 3
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_transit_secret_envelope_structure(self, initialized_db, identity_in_db):
        """Test that the envelope has correct structure for pipeline processing."""
        params = {
            "network_id": identity_in_db["network_id"],
            "identity_id": identity_in_db["identity_id"]
        }
        
        envelope = create_transit_secret(params)
        
        # Required fields for pipeline
        assert envelope["event_type"] == "transit_secret"
        assert envelope["self_created"] == True
        assert envelope["peer_id"] == identity_in_db["identity_id"]
        assert envelope["network_id"] == identity_in_db["network_id"]