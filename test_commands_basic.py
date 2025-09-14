#!/usr/bin/env python3
"""
Basic test to verify commands work without pytest dependencies.
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from protocols.quiet.events.identity.commands import create_identity
from protocols.quiet.events.group.commands import create_group
from protocols.quiet.events.channel.commands import create_channel

def test_identity_command():
    """Test identity command creates proper envelope."""
    params = {
        "network_id": "test-network",
        "name": "Test User"
    }
    
    envelope = create_identity(params)
    
    assert envelope["event_type"] == "identity"
    assert envelope["self_created"] == True
    
    event = envelope["event_plaintext"]
    assert event["type"] == "identity"
    assert event["network_id"] == "test-network"
    assert event["name"] == "Test User"
    assert event["peer_id"] != ""  # Should have generated a peer_id
    assert event["signature"] == ""  # Should be empty (unsigned)
    
    # Check secret data
    assert "secret" in envelope
    assert "private_key" in envelope["secret"]
    assert "public_key" in envelope["secret"]
    
    print("✓ Identity command test passed")

def test_group_command():
    """Test group command creates proper envelope."""
    params = {
        "name": "Engineering",
        "network_id": "test-network", 
        "identity_id": "test-identity"
    }
    
    envelope = create_group(params)
    
    assert envelope["event_type"] == "group"
    assert envelope["peer_id"] == "test-identity"
    
    event = envelope["event_plaintext"]
    assert event["type"] == "group"
    assert event["group_id"] == ""  # Should be empty (filled by encrypt handler)
    assert event["name"] == "Engineering"
    assert event["signature"] == ""  # Should be empty (unsigned)
    
    print("✓ Group command test passed")

def test_channel_command():
    """Test channel command creates proper envelope."""
    params = {
        "name": "general",
        "group_id": "test-group",
        "identity_id": "test-identity",
        "network_id": "test-network"
    }
    
    envelope = create_channel(params)
    
    assert envelope["event_type"] == "channel"
    assert envelope["deps"] == ["group:test-group"]
    
    event = envelope["event_plaintext"]
    assert event["type"] == "channel"
    assert event["channel_id"] == ""  # Should be empty (filled by encrypt handler)
    assert event["name"] == "general"
    assert event["signature"] == ""  # Should be empty (unsigned)
    
    print("✓ Channel command test passed")

if __name__ == "__main__":
    try:
        test_identity_command()
        test_group_command()
        test_channel_command()
        print("\nAll basic command tests passed!")
    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)