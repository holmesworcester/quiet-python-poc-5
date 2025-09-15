"""
Tests for network event type command (create).
"""
import pytest
import sys
import json
from pathlib import Path
from typing import Dict, Any

# Add project root to path
test_dir = Path(__file__).parent
protocol_dir = test_dir.parent.parent.parent.parent
project_root = protocol_dir.parent.parent
sys.path.insert(0, str(project_root))

from protocols.quiet.events.network.commands import create_network
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
        
        envelopes = create_network(params)

        # Should emit two envelopes: identity event and network event
        assert len(envelopes) == 2

        # First envelope should be identity event (must be created first for signing)
        identity_envelope = envelopes[0]
        network_envelope = envelopes[1]
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
        
        # Check identity envelope
        assert identity_envelope["event_type"] == "identity"
        identity_event = identity_envelope["event_plaintext"]
        assert identity_event["peer_id"] == network_event["creator_id"]
        assert identity_event["network_id"] == network_event["network_id"]
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_network_with_creator_name(self, initialized_db):
        """Test network creation with custom creator name."""
        params = {
            "name": "Test Network",
            "creator_name": "Alice"
        }
        
        envelopes = create_network(params)
        assert len(envelopes) == 2
        identity_envelope = envelopes[0]
        network_envelope = envelopes[1]

        # Check that creator identity envelope has custom name
        identity_event = identity_envelope["event_plaintext"]
        assert identity_event["name"] == "Alice"
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_network_missing_name(self, initialized_db):
        """Test that missing name raises error."""
        params: Dict[str, Any] = {}
        
        with pytest.raises(ValueError, match="name is required"):
            create_network(params)
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_network_envelope_structure(self, initialized_db):
        """Test that the envelopes have correct structure for pipeline processing."""
        params = {
            "name": "Test Network"
        }
        
        envelopes = create_network(params)
        assert len(envelopes) == 2
        identity_envelope = envelopes[0]
        network_envelope = envelopes[1]
        
        # Check network envelope
        network_envelope = network_envelope
        assert network_envelope["event_type"] == "network"
        assert network_envelope["self_created"] == True
        assert network_envelope["peer_id"] == network_envelope["event_plaintext"]["creator_id"]
        assert network_envelope["network_id"] == network_envelope["event_plaintext"]["network_id"]
        
        # Check identity envelope
        identity_envelope = identity_envelope
        assert identity_envelope["event_type"] == "identity"
        assert identity_envelope["self_created"] == True
        assert identity_envelope["peer_id"] == identity_envelope["event_plaintext"]["peer_id"]
        assert identity_envelope["network_id"] == network_envelope["event_plaintext"]["network_id"]