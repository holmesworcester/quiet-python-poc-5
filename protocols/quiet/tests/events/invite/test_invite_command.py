"""
Tests for invite event type command (create).
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

from protocols.quiet.events.invite.commands import create_invite
from protocols.quiet.events.identity.commands import create_identity
from core.crypto import verify, generate_keypair
from core.processor import PipelineRunner


class TestInviteCommand:
    """Test invite creation command."""
    
    @pytest.fixture
    def test_identity(self):
        """Create a test identity with keypair."""
        private_key, public_key = generate_keypair()
        return {
            'identity_id': public_key.hex(),
            'private_key': private_key,
            'public_key': public_key
        }
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_invite_basic(self, initialized_db):
        """Test basic invite creation."""
        # Mock identity with keypair
        from core.crypto import generate_keypair
        private_key, public_key = generate_keypair()
        identity_id = public_key.hex()
        
        params = {
            "network_id": "test-network",
            "identity_id": identity_id,
            "private_key": private_key
        }
        
        envelopes = create_invite(params, initialized_db)
        
        # Should emit exactly one envelope
        assert len(envelopes) == 1
        
        envelope = envelopes[0]
        assert "event_plaintext" in envelope
        assert "event_type" in envelope
        assert envelope["event_type"] == "invite"
        assert envelope["self_created"] == True
        
        # Check event content
        event = envelope["event_plaintext"]
        assert event["type"] == "invite"
        assert event["network_id"] == "test-network"
        assert event["inviter_id"] == identity_id
        assert "invite_code" in event
        assert "created_at" in event
        assert "expires_at" in event
        assert "signature" in event
        
        # Verify invite code format
        assert len(event["invite_code"]) > 20  # Should be reasonably long
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_invite_with_custom_code(self, initialized_db, test_identity):
        """Test invite creation with custom invite code."""
        custom_code = "custom-invite-code-123"
        params = {
            "network_id": "test-network",
            "identity_id": test_identity['identity_id'],
            "private_key": test_identity['private_key'],
            "invite_code": custom_code
        }
        
        envelopes = create_invite(params, initialized_db)
        event = envelopes[0]["event_plaintext"]
        
        assert event["invite_code"] == custom_code
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_invite_missing_network_id(self, initialized_db):
        """Test that missing network_id raises error."""
        params = {
            "identity_id": "some-identity"
        }
        
        with pytest.raises(ValueError, match="network_id is required"):
            create_invite(params, initialized_db)
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_invite_missing_identity_id(self, initialized_db):
        """Test that missing identity_id raises error."""
        params = {
            "network_id": "test-network",
            "private_key": b"dummy_key"
        }
        
        with pytest.raises(ValueError, match="identity_id is required"):
            create_invite(params, initialized_db)
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_invite_missing_private_key(self, initialized_db):
        """Test that missing private_key raises error."""
        params = {
            "network_id": "test-network",
            "identity_id": "some-identity"
        }
        
        with pytest.raises(ValueError, match="private_key is required"):
            create_invite(params, initialized_db)
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_invite_signature_valid(self, initialized_db, test_identity):
        """Test that the created invite has a valid signature."""
        params = {
            "network_id": "test-network",
            "identity_id": test_identity['identity_id'],
            "private_key": test_identity['private_key']
        }
        
        envelopes = create_invite(params, initialized_db)
        event = envelopes[0]["event_plaintext"]
        
        # Remove signature from event for verification
        signature_hex = event["signature"]
        signature = bytes.fromhex(signature_hex)
        
        # Create the message that was signed
        event_copy = event.copy()
        del event_copy["signature"]
        message = json.dumps(event_copy, sort_keys=True).encode()
        
        # Get public key from identity
        public_key = test_identity['public_key']
        
        # Verify signature
        assert verify(message, signature, public_key)
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_invite_event_structure(self, initialized_db):
        """Test that invite event has correct structure."""
        # Mock private key for testing
        from core.crypto import generate_keypair
        private_key, public_key = generate_keypair()
        identity_id = public_key.hex()
        
        params = {
            "network_id": "test-network",
            "identity_id": identity_id,
            "private_key": private_key
        }
        
        envelopes = create_invite(params, initialized_db)
        
        assert len(envelopes) == 1
        envelope = envelopes[0]
        event = envelope["event_plaintext"]
        
        # Check event structure
        assert event["type"] == "invite"
        assert event["network_id"] == "test-network"
        assert event["inviter_id"] == identity_id
        assert "invite_code" in event
        assert "created_at" in event
        assert "expires_at" in event
        assert "signature" in event
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_invite_with_custom_expiry(self, initialized_db, test_identity):
        """Test invite creation with custom expiry time."""
        import time
        custom_expiry = int(time.time() * 1000) + 3600000  # 1 hour from now
        
        params = {
            "network_id": "test-network",
            "identity_id": test_identity['identity_id'],
            "private_key": test_identity['private_key'],
            "expires_at": custom_expiry
        }
        
        envelopes = create_invite(params, initialized_db)
        event = envelopes[0]["event_plaintext"]
        
        assert event["expires_at"] == custom_expiry
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_multiple_invites(self, initialized_db, test_identity):
        """Test creating multiple invites from same identity."""
        # Create first invite
        envelopes1 = create_invite({
            "network_id": "test-network",
            "identity_id": test_identity['identity_id'],
            "private_key": test_identity['private_key']
        }, initialized_db)
        code1 = envelopes1[0]["event_plaintext"]["invite_code"]
        
        # Create second invite
        envelopes2 = create_invite({
            "network_id": "test-network",
            "identity_id": test_identity['identity_id'],
            "private_key": test_identity['private_key']
        }, initialized_db)
        code2 = envelopes2[0]["event_plaintext"]["invite_code"]
        
        # Should have different invite codes
        assert code1 != code2
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_invite_envelope_structure(self, initialized_db, test_identity):
        """Test that the envelope has correct structure for pipeline processing."""
        params = {
            "network_id": "test-network",
            "identity_id": test_identity['identity_id'],
            "private_key": test_identity['private_key']
        }
        
        envelopes = create_invite(params, initialized_db)
        envelope = envelopes[0]
        
        # Required fields for pipeline
        assert envelope["event_type"] == "invite"
        assert envelope["self_created"] == True
        assert envelope["peer_id"] == test_identity['identity_id']
        assert envelope["network_id"] == "test-network"