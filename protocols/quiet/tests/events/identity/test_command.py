"""
Tests for identity event type command (create).
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

from protocols.quiet.events.identity.commands import create_identity
from core.crypto import verify
from core.api import API


class TestIdentityCommand:
    """Test identity creation command."""
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_identity_basic(self, tmp_path):
        """Test basic identity creation."""
        # Create API client
        api = API(protocol_dir, reset_db=True, db_path=tmp_path / "test.db")
        
        # Execute command through API
        result = api.create_identity(network_id="test-network")
        
        # Check result structure
        assert "peer_id" in result
        assert "network_id" in result
        assert result["network_id"] == "test-network"
        assert "created_at" in result
        assert "signature" in result
        
        # Verify peer_id is valid hex
        assert len(result["peer_id"]) == 64  # 32 bytes as hex
        bytes.fromhex(result["peer_id"])  # Should not raise
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_identity_direct_command(self):
        """Test direct command execution (no database)."""
        params = {
            "network_id": "test-network"
        }
        
        envelope = create_identity(params)
        
        # Check envelope structure
        assert "event_plaintext" in envelope
        assert "event_type" in envelope
        assert envelope["event_type"] == "identity"
        assert envelope["self_created"] == True
        
        # Check event content
        event = envelope["event_plaintext"]
        assert event["type"] == "identity"
        assert event["network_id"] == "test-network"
        assert "peer_id" in event
        assert "created_at" in event
        assert event["signature"] == ""  # Unsigned
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_identity_through_api_stores_key(self, tmp_path):
        """Test that identity creation through API stores keys."""
        # Create API client
        api = API(protocol_dir, reset_db=True, db_path=tmp_path / "test.db")
        
        # Create identity
        result = api.create_identity(network_id="test-network")
        peer_id = result["peer_id"]
        
        # Query for stored identity
        identities = api.get_identities(network_id="test-network")
        assert len(identities) == 1
        assert identities[0]["identity_id"] == peer_id
        assert identities[0]["network_id"] == "test-network"
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_identity_with_name(self):
        """Test creating identity with custom name."""
        params = {
            "network_id": "test-network",
            "name": "Alice"
        }
        
        envelope = create_identity(params)
        event = envelope["event_plaintext"]
        
        assert event["name"] == "Alice"
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_identity_envelope_has_secret(self):
        """Test that envelope contains secret data."""
        params = {
            "network_id": "test-network"
        }
        
        envelope = create_identity(params)
        
        # Check secret data
        assert "secret" in envelope
        assert "private_key" in envelope["secret"]
        assert "public_key" in envelope["secret"]
        
        # Verify keys are valid hex
        assert len(envelope["secret"]["private_key"]) == 64  # 32 bytes as hex
        assert len(envelope["secret"]["public_key"]) == 64  # 32 bytes as hex
        
        # Verify public key matches peer_id
        assert envelope["secret"]["public_key"] == envelope["event_plaintext"]["peer_id"]