"""
Tests for user event type join command.
"""
import pytest
import sys
import json
import time
from pathlib import Path

# Add project root to path
test_dir = Path(__file__).parent
protocol_dir = test_dir.parent.parent.parent.parent
project_root = protocol_dir.parent.parent
sys.path.insert(0, str(project_root))

from protocols.quiet.events.user.commands import join_network
from protocols.quiet.events.identity.commands import create_identity
from protocols.quiet.events.invite.commands import create_invite
from core.crypto import verify


class TestJoinCommand:
    """Test join network command."""
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_join_network_basic(self, initialized_db):
        """Test basic network join with valid invite."""
        # First create an inviter identity
        inviter_envelopes = create_identity({"network_id": "test-network"}, initialized_db)
        inviter_id = inviter_envelopes[0]["event_plaintext"]["peer_id"]
        
        # Create an invite
        invite_envelopes = create_invite({
            "network_id": "test-network",
            "identity_id": inviter_id
        }, initialized_db)
        invite_code = invite_envelopes[0]["event_plaintext"]["invite_code"]
        
        # Join using the invite
        params = {
            "invite_code": invite_code
        }
        
        envelopes = join_network(params, initialized_db)
        
        # Should emit exactly one envelope (identity event)
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
        assert event["invited_by"] == inviter_id
        assert event["invite_code"] == invite_code
        assert "peer_id" in event
        assert "name" in event
        assert "created_at" in event
        assert "signature" in event
        
        # New identity should be different from inviter
        assert event["peer_id"] != inviter_id
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_join_network_with_name(self, initialized_db):
        """Test join network with custom name."""
        # Create inviter and invite
        inviter_envelopes = create_identity({"network_id": "test-network"}, initialized_db)
        inviter_id = inviter_envelopes[0]["event_plaintext"]["peer_id"]
        
        invite_envelopes = create_invite({
            "network_id": "test-network",
            "identity_id": inviter_id
        }, initialized_db)
        invite_code = invite_envelopes[0]["event_plaintext"]["invite_code"]
        
        # Join with custom name
        params = {
            "invite_code": invite_code,
            "name": "Alice"
        }
        
        envelopes = join_network(params, initialized_db)
        event = envelopes[0]["event_plaintext"]
        
        assert event["name"] == "Alice"
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_join_missing_invite_code(self, initialized_db):
        """Test that missing invite_code raises error."""
        params = {}
        
        with pytest.raises(ValueError, match="invite_code is required"):
            join_network(params, initialized_db)
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_join_invalid_invite_code(self, initialized_db):
        """Test that invalid invite code raises error."""
        params = {
            "invite_code": "invalid-invite-code"
        }
        
        with pytest.raises(ValueError, match="Invalid invite code"):
            join_network(params, initialized_db)
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_join_expired_invite(self, initialized_db):
        """Test that expired invite raises error."""
        # Create inviter
        inviter_envelopes = create_identity({"network_id": "test-network"}, initialized_db)
        inviter_id = inviter_envelopes[0]["event_plaintext"]["peer_id"]
        
        # Create an expired invite
        expired_time = int(time.time() * 1000) - 1000  # 1 second ago
        invite_envelopes = create_invite({
            "network_id": "test-network",
            "identity_id": inviter_id,
            "expires_at": expired_time
        }, initialized_db)
        invite_code = invite_envelopes[0]["event_plaintext"]["invite_code"]
        
        # Try to join with expired invite
        params = {
            "invite_code": invite_code
        }
        
        with pytest.raises(ValueError, match="Invite has expired"):
            join_network(params, initialized_db)
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_join_used_invite(self, initialized_db):
        """Test that used invite raises error."""
        # Create inviter and invite
        inviter_envelopes = create_identity({"network_id": "test-network"}, initialized_db)
        inviter_id = inviter_envelopes[0]["event_plaintext"]["peer_id"]
        
        invite_envelopes = create_invite({
            "network_id": "test-network",
            "identity_id": inviter_id
        }, initialized_db)
        invite_code = invite_envelopes[0]["event_plaintext"]["invite_code"]
        
        # Use the invite once
        join_network({"invite_code": invite_code}, initialized_db)
        
        # Try to use it again
        with pytest.raises(ValueError, match="Invite has already been used"):
            join_network({"invite_code": invite_code}, initialized_db)
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_join_signature_valid(self, initialized_db):
        """Test that the created identity has a valid signature."""
        # Create inviter and invite
        inviter_envelopes = create_identity({"network_id": "test-network"}, initialized_db)
        inviter_id = inviter_envelopes[0]["event_plaintext"]["peer_id"]
        
        invite_envelopes = create_invite({
            "network_id": "test-network",
            "identity_id": inviter_id
        }, initialized_db)
        invite_code = invite_envelopes[0]["event_plaintext"]["invite_code"]
        
        # Join
        envelopes = join_network({"invite_code": invite_code}, initialized_db)
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
    def test_join_stores_identity_in_database(self, initialized_db):
        """Test that joined identity is stored in database."""
        # Create inviter and invite
        inviter_envelopes = create_identity({"network_id": "test-network"}, initialized_db)
        inviter_id = inviter_envelopes[0]["event_plaintext"]["peer_id"]
        
        invite_envelopes = create_invite({
            "network_id": "test-network",
            "identity_id": inviter_id
        }, initialized_db)
        invite_code = invite_envelopes[0]["event_plaintext"]["invite_code"]
        
        # Join
        envelopes = join_network({
            "invite_code": invite_code,
            "name": "Bob"
        }, initialized_db)
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
        assert row["name"] == "Bob"
        assert row["private_key"] is not None
        assert row["public_key"] is not None
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_join_marks_invite_as_used(self, initialized_db):
        """Test that invite is marked as used after join."""
        # Create inviter and invite
        inviter_envelopes = create_identity({"network_id": "test-network"}, initialized_db)
        inviter_id = inviter_envelopes[0]["event_plaintext"]["peer_id"]
        
        invite_envelopes = create_invite({
            "network_id": "test-network",
            "identity_id": inviter_id
        }, initialized_db)
        invite_code = invite_envelopes[0]["event_plaintext"]["invite_code"]
        
        # Join
        envelopes = join_network({"invite_code": invite_code}, initialized_db)
        joiner_id = envelopes[0]["event_plaintext"]["peer_id"]
        
        # Check invite is marked as used
        cursor = initialized_db.cursor()
        cursor.execute(
            "SELECT used, used_by, used_at FROM invites WHERE invite_code = ?",
            (invite_code,)
        )
        
        row = cursor.fetchone()
        assert row["used"] == 1
        assert row["used_by"] == joiner_id
        assert row["used_at"] is not None
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_join_default_name_format(self, initialized_db):
        """Test that default name has expected format."""
        # Create inviter and invite
        inviter_envelopes = create_identity({"network_id": "test-network"}, initialized_db)
        inviter_id = inviter_envelopes[0]["event_plaintext"]["peer_id"]
        
        invite_envelopes = create_invite({
            "network_id": "test-network",
            "identity_id": inviter_id
        }, initialized_db)
        invite_code = invite_envelopes[0]["event_plaintext"]["invite_code"]
        
        # Join without name
        envelopes = join_network({"invite_code": invite_code}, initialized_db)
        event = envelopes[0]["event_plaintext"]
        
        # Check default name format
        assert event["name"].startswith("User-")
        assert len(event["name"]) == 13  # "User-" + 8 chars
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_join_envelope_structure(self, initialized_db):
        """Test that the envelope has correct structure for pipeline processing."""
        # Create inviter and invite
        inviter_envelopes = create_identity({"network_id": "test-network"}, initialized_db)
        inviter_id = inviter_envelopes[0]["event_plaintext"]["peer_id"]
        
        invite_envelopes = create_invite({
            "network_id": "test-network",
            "identity_id": inviter_id
        }, initialized_db)
        invite_code = invite_envelopes[0]["event_plaintext"]["invite_code"]
        
        # Join
        envelopes = join_network({"invite_code": invite_code}, initialized_db)
        envelope = envelopes[0]
        
        # Required fields for pipeline
        assert envelope["event_type"] == "identity"
        assert envelope["self_created"] == True
        assert envelope["peer_id"] == envelope["event_plaintext"]["peer_id"]
        assert envelope["network_id"] == "test-network"