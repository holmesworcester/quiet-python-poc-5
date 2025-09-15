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
        
        envelope = create_group(params)
        
        # Check envelope structure
        assert envelope["event_type"] == "group"
        assert envelope["self_created"] == True
        assert envelope["peer_id"] == "test-identity"
        assert envelope["network_id"] == "test-network"
        assert envelope["deps"] == []  # No dependencies
        
        # Check event content
        event = envelope["event_plaintext"]
        assert event["type"] == "group"
        assert event["name"] == "Engineering"
        assert event["network_id"] == "test-network"
        assert event["creator_id"] == "test-identity"
        assert event["group_id"] == ""  # Empty until handlers process
        assert "created_at" in event
        assert event["signature"] == ""  # Unsigned
    
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_group_default_values(self):
        """Test group creation with default/missing values."""
        params: Dict[str, Any] = {}
        
        envelope = create_group(params)
        event = envelope["event_plaintext"]
        
        # Should use empty defaults
        assert event["name"] == ""
        assert event["network_id"] == ""
        assert event["creator_id"] == ""
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_group_timestamp(self):
        """Test that created_at timestamp is set."""
        params = {
            "name": "Engineering",
            "network_id": "test-network",
            "identity_id": "test-identity"
        }

        envelope = create_group(params)
        event = envelope["event_plaintext"]

        # Should have timestamp and empty group_id
        assert event["group_id"] == ""  # Empty until handlers process
        assert isinstance(event["created_at"], int)
        assert event["created_at"] > 0
