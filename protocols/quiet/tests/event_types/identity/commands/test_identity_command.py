"""
Tests for identity event type command (create).
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

from protocols.quiet.event_types.identity.commands.create import create_identity
from core.crypto import verify


class TestIdentityCommand:
    """Test identity creation command."""
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_identity_basic(self, initialized_db):
        """Test basic identity creation."""
        params = {
            "network_id": "test-network"
        }
        
        envelopes = create_identity(params, initialized_db)
        
        # Should emit exactly one envelope
        assert len(envelopes) == 1
        
        envelope = envelopes[0]
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
        assert "signature" in event
        
        # Verify peer_id is valid hex
        assert len(event["peer_id"]) == 64  # 32 bytes as hex
        bytes.fromhex(event["peer_id"])  # Should not raise
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_identity_missing_network_id(self, initialized_db):
        """Test that missing network_id raises error."""
        params = {}
        
        with pytest.raises(ValueError, match="network_id is required"):
            create_identity(params, initialized_db)
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_identity_signature_valid(self, initialized_db):
        """Test that the created identity has a valid signature."""
        params = {
            "network_id": "test-network"
        }
        
        envelopes = create_identity(params, initialized_db)
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
    def test_create_identity_stores_private_key(self, initialized_db):
        """Test that private key is stored in database."""
        params = {
            "network_id": "test-network"
        }
        
        envelopes = create_identity(params, initialized_db)
        peer_id = envelopes[0]["event_plaintext"]["peer_id"]
        
        # Check database for stored identity
        cursor = initialized_db.cursor()
        cursor.execute(
            "SELECT * FROM identities WHERE identity_id = ?",
            (peer_id,)
        )
        
        row = cursor.fetchone()
        assert row is not None
        assert row["network_id"] == "test-network"
        assert row["private_key"] is not None
        assert row["public_key"] is not None
        assert len(row["private_key"]) == 32  # 32 bytes
        assert len(row["public_key"]) == 32  # 32 bytes
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_multiple_identities(self, initialized_db):
        """Test creating multiple identities on same network."""
        network_id = "test-network"
        
        # Create first identity
        envelopes1 = create_identity({"network_id": network_id}, initialized_db)
        peer_id1 = envelopes1[0]["event_plaintext"]["peer_id"]
        
        # Create second identity
        envelopes2 = create_identity({"network_id": network_id}, initialized_db)
        peer_id2 = envelopes2[0]["event_plaintext"]["peer_id"]
        
        # Should have different peer IDs
        assert peer_id1 != peer_id2
        
        # Both should be in database
        cursor = initialized_db.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM identities WHERE network_id = ?", (network_id,))
        assert cursor.fetchone()["count"] == 2
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_identity_envelope_structure(self, initialized_db):
        """Test that the envelope has correct structure for pipeline processing."""
        params = {
            "network_id": "test-network"
        }
        
        envelopes = create_identity(params, initialized_db)
        envelope = envelopes[0]
        
        # Required fields for pipeline
        assert envelope["event_type"] == "identity"
        assert envelope["self_created"] == True
        assert envelope["peer_id"] == envelope["event_plaintext"]["peer_id"]
        assert envelope["network_id"] == "test-network"