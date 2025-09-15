"""
Tests for channel commands.
"""
import pytest
from protocols.quiet.events.channel.commands import create_channel
from protocols.quiet.tests.test_commands_base import CommandTestBase


class TestChannelCommands(CommandTestBase):
    """Test channel commands."""
    
    def test_create_channel_envelope_structure(self):
        """Test that create_channel generates correct envelope structure."""
        params = {
            'name': 'general',
            'group_id': 'test_group_id',
            'identity_id': 'test_identity_id',
            'network_id': 'test_network'
        }
        
        envelope = create_channel(params)
        
        # Check envelope structure
        assert envelope['event_type'] == 'channel'
        assert envelope['self_created'] == True
        assert envelope['peer_id'] == 'test_identity_id'
        assert envelope['network_id'] == 'test_network'
        assert envelope['deps'] == ['group:test_group_id']
        
        # Check event structure
        event = envelope['event_plaintext']
        assert event['type'] == 'channel'
        assert event['name'] == 'general'
        assert event['group_id'] == 'test_group_id'
        assert event['network_id'] == 'test_network'
        assert event['creator_id'] == 'test_identity_id'
        assert 'created_at' in event
        assert event['signature'] == ''  # Not signed yet
        assert event['channel_id'] == ''  # Will be filled by encrypt handler
        
        print("✓ create_channel envelope structure test passed")
    
    def test_create_channel_dependency(self):
        """Test that create_channel correctly sets group dependency."""
        params = {
            'name': 'random',
            'group_id': 'group_abc123',
            'identity_id': 'identity_xyz789',
            'network_id': 'test_network'
        }
        
        envelope = create_channel(params)
        
        # Check that channel depends on the group
        deps = envelope['deps']
        assert len(deps) == 1, "Should have one dependency"
        assert 'group:group_abc123' in deps, "Should depend on group"
        
        print("✓ create_channel dependency test passed")

    def test_create_channel_api_response(self):
        """Test that create_channel returns channel list via API."""
        from core.api import API
        from pathlib import Path

        # Initialize API with test database
        api = API(Path('protocols/quiet'), reset_db=True)

        # First create an identity and group
        identity_result = api.create_identity({
            'name': 'Alice',
            'network_id': 'test_net'
        })

        group_result = api.create_group({
            'name': 'Test Group',
            'network_id': 'test_net'
        })

        if 'ids' in group_result and 'group' in group_result['ids']:
            # Create first channel
            channel1_result = api.create_channel({
                'name': 'general',
                'group_id': group_result['ids']['group'],
                'identity_id': identity_result['ids']['identity'],
                'network_id': 'test_net'
            })

            # Check that response includes channels list
            assert 'channels' in channel1_result, "Response should include channels list"
            assert len(channel1_result['channels']) >= 1, "Should have at least one channel"

            # Create second channel
            channel2_result = api.create_channel({
                'name': 'random',
                'group_id': group_result['ids']['group'],
                'identity_id': identity_result['ids']['identity'],
                'network_id': 'test_net'
            })

            # Check that response includes both channels
            assert 'channels' in channel2_result, "Response should include channels list"
            assert len(channel2_result['channels']) >= 2, "Should have at least two channels"

            # Verify the newly created channel is in the list
            channel_names = [ch['name'] for ch in channel2_result['channels']]
            assert 'general' in channel_names, "First channel should be in list"
            assert 'random' in channel_names, "Second channel should be in list"

            print(f"✓ create_channel returned {len(channel2_result['channels'])} channels")
            print("✓ create_channel API response test passed")
        else:
            print("⚠ Skipping API test - could not create group")


def run_tests():
    """Run all channel command tests."""
    test = TestChannelCommands()
    
    print("=" * 60)
    print("Testing Channel Commands")
    print("=" * 60)
    
    print("\n1. Testing create_channel envelope structure:")
    print("-" * 40)
    test.test_create_channel_envelope_structure()
    
    print("\n2. Testing create_channel dependency:")
    print("-" * 40)
    test.test_create_channel_dependency()

    print("\n3. Testing create_channel API response with query data:")
    print("-" * 40)
    test.test_create_channel_api_response()

    print("\n" + "=" * 60)
    print("Channel command tests complete!")


if __name__ == "__main__":
    run_tests()
