"""
Tests for group commands.
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))

from protocols.quiet.events.group.commands import create_group
from protocols.quiet.tests.test_commands_base import CommandTestBase


class TestGroupCommands(CommandTestBase):
    """Test group commands."""
    
    def test_create_group_envelope_structure(self):
        """Test that create_group generates correct envelope structure."""
        params = {
            'name': 'Test Community',
            'network_id': 'test_network',
            'identity_id': 'test_identity_id'
        }
        
        envelope = create_group(params)
        
        # Check envelope structure
        assert envelope['event_type'] == 'group'
        assert envelope['self_created'] == True
        assert envelope['peer_id'] == 'test_identity_id'
        assert envelope['network_id'] == 'test_network'
        assert envelope['deps'] == []  # Groups have no dependencies
        
        # Check event structure
        event = envelope['event_plaintext']
        assert event['type'] == 'group'
        assert event['name'] == 'Test Community'
        assert event['network_id'] == 'test_network'
        assert event['creator_id'] == 'test_identity_id'
        assert event['group_id'] == ''  # Will be filled by encrypt handler
        assert 'created_at' in event
        assert event['signature'] == ''  # Not signed yet
        
        print("✓ create_group envelope structure test passed")
    
    def test_create_group_no_dependencies(self):
        """Test that create_group has no dependencies."""
        params = {
            'name': 'Independent Group',
            'network_id': 'test_network',
            'identity_id': 'identity_abc123'
        }
        
        envelope = create_group(params)
        
        # Groups should not depend on any other events
        assert envelope['deps'] == [], "Groups should have no dependencies"
        
        print("✓ create_group no dependencies test passed")

    def test_create_group_api_response(self):
        """Test that create_group returns list of all groups via API."""
        from core.api import API
        from pathlib import Path

        # Initialize API with test database
        api = API(Path('protocols/quiet'), reset_db=True)

        # First create an identity (required for group creation)
        identity_result = api.create_identity({
            'name': 'Alice',
            'network_id': 'test_net'
        })

        identity_id = identity_result['ids']['identity']

        # Create first group
        group1_result = api.create_group({
            'name': 'First Group',
            'network_id': 'test_net',
            'identity_id': identity_id
        })

        # Check that response includes groups list
        assert 'groups' in group1_result, "Response should include groups list"
        assert len(group1_result['groups']) >= 1, "Should have at least one group"

        # Create second group
        group2_result = api.create_group({
            'name': 'Second Group',
            'network_id': 'test_net',
            'identity_id': identity_id
        })

        # Check that response includes both groups
        assert 'groups' in group2_result, "Response should include groups list"
        assert len(group2_result['groups']) >= 2, "Should have at least two groups"

        # Verify both groups are in the list
        group_names = [g['name'] for g in group2_result['groups']]
        assert 'First Group' in group_names, "First group should be in list"
        assert 'Second Group' in group_names, "Second group should be in list"

        print(f"✓ create_group returned {len(group2_result['groups'])} groups")
        print("✓ create_group API response test passed")


def run_tests():
    """Run all group command tests."""
    test = TestGroupCommands()
    
    print("=" * 60)
    print("Testing Group Commands")
    print("=" * 60)
    
    print("\n1. Testing create_group envelope structure:")
    print("-" * 40)
    test.test_create_group_envelope_structure()
    
    print("\n2. Testing create_group no dependencies:")
    print("-" * 40)
    test.test_create_group_no_dependencies()

    print("\n3. Testing create_group API response with query data:")
    print("-" * 40)
    test.test_create_group_api_response()

    print("\n" + "=" * 60)
    print("Group command tests complete!")


if __name__ == "__main__":
    run_tests()
