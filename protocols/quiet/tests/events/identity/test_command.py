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


class TestIdentityCommand:
    """Test identity creation command."""
    
    
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