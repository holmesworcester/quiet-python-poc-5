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
from protocols.quiet.events.identity.commands import create_identity
from core.crypto import verify


class TestTransitSecretCommand:
    """Test transit secret creation command."""
    
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
    def test_create_transit_secret_basic(self, initialized_db, identity_in_db):
        """Test basic transit secret creation."""
        params = {
            "network_id": identity_in_db["network_id"],
            "identity_id": identity_in_db["identity_id"]
        }
        
        envelopes = create_transit_secret(params, initialized_db)
        
        # Should emit exactly one envelope
        assert len(envelopes) == 1
        
        envelope = envelopes[0]
        assert "event_plaintext" in envelope
        assert "event_type" in envelope
        assert envelope["event_type"] == "transit_secret"
        assert envelope["self_created"] == True
        
        # Check event content
        event = envelope["event_plaintext"]
        assert event["type"] == "transit_secret"
        assert event["network_id"] == "test-network"
        assert event["peer_id"] == identity_in_db["identity_id"]
        assert "transit_key_id" in event
        assert "created_at" in event
        assert "signature" in event
        
        # Should NOT contain the actual secret
        assert "secret" not in event
        assert "encrypted_secret" not in event
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_transit_secret_missing_network_id(self, initialized_db, identity_in_db):
        """Test that missing network_id raises error."""
        params = {
            "identity_id": identity_in_db["identity_id"]
        }
        
        with pytest.raises(ValueError, match="network_id is required"):
            create_transit_secret(params, initialized_db)
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_transit_secret_missing_identity_id(self, initialized_db):
        """Test that missing identity_id raises error."""
        params = {
            "network_id": "test-network"
        }
        
        with pytest.raises(ValueError, match="identity_id is required"):
            create_transit_secret(params, initialized_db)
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_transit_secret_invalid_identity(self, initialized_db):
        """Test that invalid identity_id raises error."""
        params = {
            "network_id": "test-network",
            "identity_id": "non-existent-identity"
        }
        
        with pytest.raises(ValueError, match="Identity .* not found"):
            create_transit_secret(params, initialized_db)
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_transit_secret_signature_valid(self, initialized_db, identity_in_db):
        """Test that the created transit secret has a valid signature."""
        params = {
            "network_id": identity_in_db["network_id"],
            "identity_id": identity_in_db["identity_id"]
        }
        
        envelopes = create_transit_secret(params, initialized_db)
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
    def test_create_transit_secret_stores_secret(self, initialized_db, identity_in_db):
        """Test that the secret is stored in the database."""
        params = {
            "network_id": identity_in_db["network_id"],
            "identity_id": identity_in_db["identity_id"]
        }
        
        envelopes = create_transit_secret(params, initialized_db)
        transit_key_id = envelopes[0]["event_plaintext"]["transit_key_id"]
        
        # Check database for stored secret
        cursor = initialized_db.cursor()
        cursor.execute(
            "SELECT * FROM transit_keys WHERE key_id = ?",
            (transit_key_id,)
        )
        
        row = cursor.fetchone()
        assert row is not None
        assert row["network_id"] == "test-network"
        assert row["secret"] is not None
        assert len(row["secret"]) == 32  # 32 bytes secret
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_transit_secret_unique_key_ids(self, initialized_db, identity_in_db):
        """Test that multiple transit secrets have unique IDs."""
        params = {
            "network_id": identity_in_db["network_id"],
            "identity_id": identity_in_db["identity_id"]
        }
        
        # Create three transit secrets
        key_ids = []
        for i in range(3):
            envelopes = create_transit_secret(params, initialized_db)
            key_id = envelopes[0]["event_plaintext"]["transit_key_id"]
            key_ids.append(key_id)
        
        # All key IDs should be unique
        assert len(set(key_ids)) == 3
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_transit_secret_envelope_structure(self, initialized_db, identity_in_db):
        """Test that the envelope has correct structure for pipeline processing."""
        params = {
            "network_id": identity_in_db["network_id"],
            "identity_id": identity_in_db["identity_id"]
        }
        
        envelopes = create_transit_secret(params, initialized_db)
        envelope = envelopes[0]
        
        # Required fields for pipeline
        assert envelope["event_type"] == "transit_secret"
        assert envelope["self_created"] == True
        assert envelope["peer_id"] == identity_in_db["identity_id"]
        assert envelope["network_id"] == identity_in_db["network_id"]