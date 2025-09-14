#!/usr/bin/env python3
"""
Basic integration test to verify commands work through the pipeline.
"""
import sys
import tempfile
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.api import API
from core.db import get_connection

def test_create_network_integration():
    """Test creating a network through the full pipeline."""
    # Create temporary directory for test
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        protocol_dir = Path(project_root) / "protocols" / "quiet"
        
        # Create API client
        api = API(protocol_dir, reset_db=True, db_path=db_path)
        
        # Create network
        result = api.create_network(name="Test Network", description="Test description")
        
        # Check result
        assert "network_id" in result
        assert result["name"] == "Test Network"
        assert result["description"] == "Test description"
        assert "creator_id" in result
        assert "signature" in result
        assert result["signature"] != ""  # Should be signed
        
        # The network_id should now be set (not empty)
        assert result["network_id"] != ""
        
        print(f"✓ Created network with ID: {result['network_id']}")
        
        # Check database state
        db = get_connection(str(db_path))
        
        # Check events table
        cursor = db.execute("SELECT * FROM events WHERE event_type = 'network'")
        events = cursor.fetchall()
        assert len(events) == 1
        
        # Check networks projection
        cursor = db.execute("SELECT * FROM networks")
        networks = cursor.fetchall()
        assert len(networks) == 1
        assert networks[0]["name"] == "Test Network"
        
        # Check identities were created
        cursor = db.execute("SELECT * FROM identities")
        identities = cursor.fetchall()
        assert len(identities) == 1
        
        db.close()
        print("✓ Database state verified")

def test_create_group_integration():
    """Test creating a group through the full pipeline."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        protocol_dir = Path(project_root) / "protocols" / "quiet"
        
        # Create API client
        api = API(protocol_dir, reset_db=True, db_path=db_path)
        
        # First create network
        network_result = api.create_network(name="Test Network")
        network_id = network_result["network_id"]
        identity_id = network_result["creator_id"]
        
        # Create group
        group_result = api.create_group(
            name="Engineering",
            network_id=network_id,
            identity_id=identity_id
        )
        
        # Check result
        assert "group_id" in group_result
        assert group_result["group_id"] != ""  # Should be filled by encrypt handler
        assert group_result["name"] == "Engineering"
        assert group_result["signature"] != ""
        
        print(f"✓ Created group with ID: {group_result['group_id']}")
        
        # Check database
        db = get_connection(str(db_path))
        
        # Check groups projection
        cursor = db.execute("SELECT * FROM groups")
        groups = cursor.fetchall()
        assert len(groups) == 1
        assert groups[0]["name"] == "Engineering"
        assert groups[0]["group_id"] == group_result["group_id"]
        
        # Check group members
        cursor = db.execute("SELECT * FROM group_members")
        members = cursor.fetchall()
        assert len(members) == 1
        assert members[0]["group_id"] == group_result["group_id"]
        assert members[0]["user_id"] == identity_id
        
        db.close()
        print("✓ Group database state verified")

def test_create_channel_integration():
    """Test creating a channel through the full pipeline."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        protocol_dir = Path(project_root) / "protocols" / "quiet"
        
        # Create API client
        api = API(protocol_dir, reset_db=True, db_path=db_path)
        
        # Create network
        network_result = api.create_network(name="Test Network")
        network_id = network_result["network_id"]
        identity_id = network_result["creator_id"]
        
        # Create group
        group_result = api.create_group(
            name="Engineering",
            network_id=network_id,
            identity_id=identity_id
        )
        group_id = group_result["group_id"]
        
        # Create channel
        channel_result = api.create_channel(
            name="general",
            group_id=group_id,
            identity_id=identity_id,
            network_id=network_id
        )
        
        # Check result
        assert "channel_id" in channel_result
        assert channel_result["channel_id"] != ""
        assert channel_result["name"] == "general"
        assert channel_result["group_id"] == group_id
        
        print(f"✓ Created channel with ID: {channel_result['channel_id']}")
        
        # Check database
        db = get_connection(str(db_path))
        
        cursor = db.execute("SELECT * FROM channels")
        channels = cursor.fetchall()
        assert len(channels) == 1
        assert channels[0]["name"] == "general"
        assert channels[0]["channel_id"] == channel_result["channel_id"]
        
        db.close()
        print("✓ Channel database state verified")

if __name__ == "__main__":
    try:
        test_create_network_integration()
        print()
        test_create_group_integration()
        print()
        test_create_channel_integration()
        print("\nAll integration tests passed!")
    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)