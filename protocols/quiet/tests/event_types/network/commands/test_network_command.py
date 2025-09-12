"""
Tests for network event type command (create).
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

from protocols.quiet.event_types.network.commands.create import create_network
from core.crypto import verify


class TestNetworkCommand:
    """Test network creation command."""
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_network_basic(self, initialized_db):
        """Test basic network creation."""
        params = {
            "name": "Test Network"
        }
        
        envelopes = create_network(params, initialized_db)
        
        # Should emit two envelopes: network event and creator identity event
        assert len(envelopes) == 2
        
        # First envelope should be network event
        network_envelope = envelopes[0]
        assert "event_plaintext" in network_envelope
        assert "event_type" in network_envelope
        assert network_envelope["event_type"] == "network"
        assert network_envelope["self_created"] == True
        
        # Check network event content
        network_event = network_envelope["event_plaintext"]
        assert network_event["type"] == "network"
        assert network_event["name"] == "Test Network"
        assert "network_id" in network_event
        assert "creator_id" in network_event
        assert "created_at" in network_event
        assert "signature" in network_event
        
        # Second envelope should be identity event
        identity_envelope = envelopes[1]
        assert identity_envelope["event_type"] == "identity"
        identity_event = identity_envelope["event_plaintext"]
        assert identity_event["peer_id"] == network_event["creator_id"]
        assert identity_event["network_id"] == network_event["network_id"]
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_network_with_description(self, initialized_db):
        """Test network creation with description."""
        params = {
            "name": "Test Network",
            "description": "A test network for unit tests"
        }
        
        envelopes = create_network(params, initialized_db)
        network_event = envelopes[0]["event_plaintext"]
        
        assert network_event["description"] == "A test network for unit tests"
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_network_with_creator_name(self, initialized_db):
        """Test network creation with custom creator name."""
        params = {
            "name": "Test Network",
            "creator_name": "Alice"
        }
        
        envelopes = create_network(params, initialized_db)
        
        # Check that creator identity is stored with custom name
        creator_id = envelopes[0]["event_plaintext"]["creator_id"]
        cursor = initialized_db.cursor()
        cursor.execute(
            "SELECT name FROM identities WHERE identity_id = ?",
            (creator_id,)
        )
        row = cursor.fetchone()
        assert row["name"] == "Alice"
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_network_missing_name(self, initialized_db):
        """Test that missing name raises error."""
        params = {}
        
        with pytest.raises(ValueError, match="name is required"):
            create_network(params, initialized_db)
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_network_signature_valid(self, initialized_db):
        """Test that the created network has a valid signature."""
        params = {
            "name": "Test Network"
        }
        
        envelopes = create_network(params, initialized_db)
        network_event = envelopes[0]["event_plaintext"]
        
        # Remove signature from event for verification
        signature_hex = network_event["signature"]
        signature = bytes.fromhex(signature_hex)
        
        # Create the message that was signed
        event_copy = network_event.copy()
        del event_copy["signature"]
        message = json.dumps(event_copy, sort_keys=True).encode()
        
        # Get public key (creator_id)
        public_key = bytes.fromhex(network_event["creator_id"])
        
        # Verify signature
        assert verify(message, signature, public_key)
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_network_identity_signature_valid(self, initialized_db):
        """Test that the creator identity has a valid signature."""
        params = {
            "name": "Test Network"
        }
        
        envelopes = create_network(params, initialized_db)
        identity_event = envelopes[1]["event_plaintext"]
        
        # Remove signature from event for verification
        signature_hex = identity_event["signature"]
        signature = bytes.fromhex(signature_hex)
        
        # Create the message that was signed
        event_copy = identity_event.copy()
        del event_copy["signature"]
        message = json.dumps(event_copy, sort_keys=True).encode()
        
        # Get public key
        public_key = bytes.fromhex(identity_event["peer_id"])
        
        # Verify signature
        assert verify(message, signature, public_key)
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_network_stores_in_database(self, initialized_db):
        """Test that network is stored in database."""
        params = {
            "name": "Test Network",
            "description": "Test description"
        }
        
        envelopes = create_network(params, initialized_db)
        network_id = envelopes[0]["event_plaintext"]["network_id"]
        creator_id = envelopes[0]["event_plaintext"]["creator_id"]
        
        # Check database for stored network
        cursor = initialized_db.cursor()
        cursor.execute(
            "SELECT * FROM networks WHERE network_id = ?",
            (network_id,)
        )
        
        row = cursor.fetchone()
        assert row is not None
        assert row["name"] == "Test Network"
        assert row["description"] == "Test description"
        assert row["creator_id"] == creator_id
        assert row["created_at"] is not None
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_network_stores_creator_identity(self, initialized_db):
        """Test that creator identity is stored in database."""
        params = {
            "name": "Test Network"
        }
        
        envelopes = create_network(params, initialized_db)
        network_id = envelopes[0]["event_plaintext"]["network_id"]
        creator_id = envelopes[0]["event_plaintext"]["creator_id"]
        
        # Check database for stored identity
        cursor = initialized_db.cursor()
        cursor.execute(
            "SELECT * FROM identities WHERE identity_id = ?",
            (creator_id,)
        )
        
        row = cursor.fetchone()
        assert row is not None
        assert row["network_id"] == network_id
        assert row["private_key"] is not None
        assert row["public_key"] is not None
        assert len(row["private_key"]) == 32  # 32 bytes
        assert len(row["public_key"]) == 32  # 32 bytes
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_network_unique_ids(self, initialized_db):
        """Test that multiple networks have unique IDs."""
        # Create first network
        envelopes1 = create_network({"name": "Network 1"}, initialized_db)
        network_id1 = envelopes1[0]["event_plaintext"]["network_id"]
        
        # Create second network
        envelopes2 = create_network({"name": "Network 2"}, initialized_db)
        network_id2 = envelopes2[0]["event_plaintext"]["network_id"]
        
        # Should have different network IDs
        assert network_id1 != network_id2
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_network_id_format(self, initialized_db):
        """Test that network ID has expected format."""
        params = {
            "name": "Test Network"
        }
        
        envelopes = create_network(params, initialized_db)
        network_id = envelopes[0]["event_plaintext"]["network_id"]
        
        # Should be a reasonable length URL-safe string
        assert len(network_id) > 10
        assert all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_' for c in network_id)
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_network_default_description(self, initialized_db):
        """Test that network has empty description by default."""
        params = {
            "name": "Test Network"
        }
        
        envelopes = create_network(params, initialized_db)
        network_event = envelopes[0]["event_plaintext"]
        
        assert network_event["description"] == ""
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_network_envelope_structure(self, initialized_db):
        """Test that the envelopes have correct structure for pipeline processing."""
        params = {
            "name": "Test Network"
        }
        
        envelopes = create_network(params, initialized_db)
        
        # Check network envelope
        network_envelope = envelopes[0]
        assert network_envelope["event_type"] == "network"
        assert network_envelope["self_created"] == True
        assert network_envelope["peer_id"] == network_envelope["event_plaintext"]["creator_id"]
        assert network_envelope["network_id"] == network_envelope["event_plaintext"]["network_id"]
        
        # Check identity envelope
        identity_envelope = envelopes[1]
        assert identity_envelope["event_type"] == "identity"
        assert identity_envelope["self_created"] == True
        assert identity_envelope["peer_id"] == identity_envelope["event_plaintext"]["peer_id"]
        assert identity_envelope["network_id"] == network_envelope["event_plaintext"]["network_id"]