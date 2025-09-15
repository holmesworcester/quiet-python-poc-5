"""
Tests for group event type command (create).
"""
import pytest
import sys
import time
from pathlib import Path
from typing import Dict, Any

# Add project root to path
test_dir = Path(__file__).parent
protocol_dir = test_dir.parent.parent.parent.parent
project_root = protocol_dir.parent.parent
sys.path.insert(0, str(project_root))

from protocols.quiet.events.group.commands import create_group


class TestGroupCommand:
    """Test group creation command."""
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_group_basic(self):
        """Test basic group creation."""
        params = {
            "name": "Engineering",
            "network_id": "test-network",
            "identity_id": "test-identity"
        }
        
        envelopes = create_group(params)

        # Should return two envelopes: group and member
        assert len(envelopes) == 2

        # Check group envelope structure
        group_envelope = envelopes[0]
        assert group_envelope["event_type"] == "group"
        assert group_envelope["self_created"] == True
        assert group_envelope["peer_id"] == "test-identity"
        assert group_envelope["network_id"] == "test-network"
        assert group_envelope["deps"] == []  # No dependencies

        # Check group event content
        group_event = group_envelope["event_plaintext"]
        assert group_event["type"] == "group"
        assert group_event["name"] == "Engineering"
        assert group_event["network_id"] == "test-network"
        assert group_event["creator_id"] == "test-identity"
        assert group_event["group_id"] == ""  # Empty until handlers process
        assert "created_at" in group_event
        assert group_event["signature"] == ""  # Unsigned

        # Check member envelope structure
        member_envelope = envelopes[1]
        assert member_envelope["event_type"] == "member"
        assert member_envelope["self_created"] == True
        assert member_envelope["peer_id"] == "test-identity"
        assert member_envelope["network_id"] == "test-network"
        assert member_envelope["deps"] == ['group:']  # Depends on group

        # Check member event content
        member_event = member_envelope["event_plaintext"]
        assert member_event["type"] == "member"
        assert member_event["user_id"] == "test-identity"
        assert member_event["added_by"] == "test-identity"
        assert member_event["group_id"] == ""  # Empty until handlers process
        assert "created_at" in member_event
        assert member_event["signature"] == ""  # Unsigned
    
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_group_default_values(self):
        """Test group creation with default/missing values."""
        params: Dict[str, Any] = {}
        
        envelopes = create_group(params)
        event = envelopes[0]["event_plaintext"]
        
        # Should use sensible defaults
        assert event["name"] == "unnamed-group"
        assert event["network_id"] == "dummy-network-id"
        assert event["creator_id"] == "dummy-identity-id"
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_group_timestamp(self):
        """Test that created_at timestamp is set."""
        params = {
            "name": "Engineering",
            "network_id": "test-network",
            "identity_id": "test-identity"
        }

        envelopes = create_group(params)
        event = envelopes[0]["event_plaintext"]

        # Should have timestamp and empty group_id
        assert event["group_id"] == ""  # Empty until handlers process
        assert isinstance(event["created_at"], int)
        assert event["created_at"] > 0
