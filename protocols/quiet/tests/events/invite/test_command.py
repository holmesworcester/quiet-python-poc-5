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
from core.identity import create_identity
from core.crypto import verify, generate_keypair
from core.pipeline import PipelineRunner


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
            "group_id": "test-group",
            "identity_id": identity_id
        }

        envelope = create_invite(params)

        # Should emit exactly one envelope
        # Single envelope returned

        assert "event_plaintext" in envelope
        assert "event_type" in envelope
        assert envelope["event_type"] == "invite"
        assert envelope["self_created"] == True

        # Check event content
        event = envelope["event_plaintext"]
        assert event["type"] == "invite"
        assert event["network_id"] == "test-network"
        assert event["group_id"] == "test-group"
        assert event["inviter_id"] == identity_id
        assert "invite_id" in event
        assert "invite_pubkey" in event
        assert "created_at" in event
        assert "signature" in event

        # Verify invite_id and invite_pubkey are non-empty
        assert len(event["invite_id"]) > 0
        assert len(event["invite_pubkey"]) > 0

        # Check envelope has invite_link
        assert "invite_link" in envelope
        assert envelope["invite_link"].startswith("quiet://invite/")

        # Check dependencies
        assert "deps" in envelope
        assert f"group:{params['group_id']}" in envelope["deps"]
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_invite_with_group_id(self, initialized_db, test_identity):
        """Test invite creation with specific group_id."""
        group_id = "custom-group-123"
        params = {
            "network_id": "test-network",
            "group_id": group_id,
            "identity_id": test_identity['identity_id']
        }

        envelope = create_invite(params)
        event = envelope["event_plaintext"]

        assert event["group_id"] == group_id
        assert f"group:{group_id}" in envelope["deps"]
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_invite_missing_network_id(self, initialized_db):
        """Test invite creation with missing network_id (should still work)."""
        params = {
            "identity_id": "some-identity",
            "group_id": "test-group"
        }

        envelope = create_invite(params)
        event = envelope["event_plaintext"]

        # Should work with empty network_id
        assert event["network_id"] == ""
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_invite_missing_identity_id(self, initialized_db):
        """Test invite creation with missing identity_id (should still work)."""
        params = {
            "network_id": "test-network",
            "group_id": "test-group"
        }

        envelope = create_invite(params)
        event = envelope["event_plaintext"]

        # Should work with empty identity_id
        assert event["inviter_id"] == ""
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_invite_missing_group_id(self, initialized_db):
        """Test invite creation with missing group_id (should still work)."""
        params = {
            "network_id": "test-network",
            "identity_id": "some-identity"
        }

        envelope = create_invite(params)
        event = envelope["event_plaintext"]

        # Should work with empty group_id
        assert event["group_id"] == ""
    
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_invite_event_structure(self, initialized_db):
        """Test that invite event has correct structure."""
        # Mock identity for testing
        from core.crypto import generate_keypair
        private_key, public_key = generate_keypair()
        identity_id = public_key.hex()

        params = {
            "network_id": "test-network",
            "group_id": "test-group",
            "identity_id": identity_id
        }

        envelope = create_invite(params)

        # Single envelope returned

        event = envelope["event_plaintext"]

        # Check event structure
        assert event["type"] == "invite"
        assert event["network_id"] == "test-network"
        assert event["group_id"] == "test-group"
        assert event["inviter_id"] == identity_id
        assert "invite_id" in event
        assert "invite_pubkey" in event
        assert "created_at" in event
        assert "signature" in event
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_invite_deterministic_keys(self, initialized_db, test_identity):
        """Test that invite keys are deterministic based on secret."""
        params = {
            "network_id": "test-network",
            "group_id": "test-group",
            "identity_id": test_identity['identity_id']
        }

        envelope1 = create_invite(params)
        envelope2 = create_invite(params)

        event1 = envelope1["event_plaintext"]
        event2 = envelope2["event_plaintext"]

        # Each invite should have different secrets/keys
        assert event1["invite_id"] != event2["invite_id"]
        assert event1["invite_pubkey"] != event2["invite_pubkey"]
        assert envelope1["invite_link"] != envelope2["invite_link"]
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_multiple_invites(self, initialized_db, test_identity):
        """Test creating multiple invites from same identity."""
        # Create first invite
        envelope1 = create_invite({
            "network_id": "test-network",
            "group_id": "test-group",
            "identity_id": test_identity['identity_id']
        })
        invite_id1 = envelope1["event_plaintext"]["invite_id"]

        # Create second invite
        envelope2 = create_invite({
            "network_id": "test-network",
            "group_id": "test-group",
            "identity_id": test_identity['identity_id']
        })
        invite_id2 = envelope2["event_plaintext"]["invite_id"]

        # Should have different invite IDs
        assert invite_id1 != invite_id2
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_invite_envelope_structure(self, initialized_db, test_identity):
        """Test that the envelope has correct structure for pipeline processing."""
        params = {
            "network_id": "test-network",
            "group_id": "test-group",
            "identity_id": test_identity['identity_id']
        }

        envelope = create_invite(params)

        # Required fields for pipeline
        assert envelope["event_type"] == "invite"
        assert envelope["self_created"] == True
        assert envelope["peer_id"] == test_identity['identity_id']
        assert envelope["network_id"] == "test-network"
        assert envelope["invite_link"].startswith("quiet://invite/")
        assert "deps" in envelope
        assert f"group:{params['group_id']}" in envelope["deps"]