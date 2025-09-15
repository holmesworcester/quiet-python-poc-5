"""
Tests for message commands.
"""
import pytest
from protocols.quiet.events.message.commands import create_message
from protocols.quiet.tests.test_commands_base import CommandTestBase


class TestMessageCommands(CommandTestBase):
    """Test message commands."""
    
    def test_create_message_envelope_structure(self):
        """Test that create_message generates correct envelope structure."""
        params = {
            'content': 'Hello, world!',
            'channel_id': 'test_channel_id',
            'identity_id': 'test_identity_id'
        }
        
        envelope = create_message(params)
        
        # Check envelope structure
        assert envelope['event_type'] == 'message'
        assert envelope['self_created'] == True
        assert envelope['peer_id'] == 'test_identity_id'
        assert envelope['network_id'] == ''  # Will be filled by resolve_deps
        assert 'identity:test_identity_id' in envelope['deps']
        assert 'channel:test_channel_id' in envelope['deps']
        
        # Check event structure
        event = envelope['event_plaintext']
        assert event['type'] == 'message'
        assert event['content'] == 'Hello, world!'
        assert event['channel_id'] == 'test_channel_id'
        assert event['peer_id'] == 'test_identity_id'
        assert event['message_id'] == ''  # Will be filled by encrypt handler
        assert event['group_id'] == ''  # Will be filled by resolve_deps
        assert event['network_id'] == ''  # Will be filled by resolve_deps
        assert 'created_at' in event
        assert event['signature'] == ''  # Not signed yet
        
        print("✓ create_message envelope structure test passed")
    
    def test_create_message_dependencies(self):
        """Test that create_message correctly sets dependencies."""
        params = {
            'content': 'Test message',
            'channel_id': 'channel_abc123',
            'identity_id': 'identity_xyz789'
        }
        
        envelope = create_message(params)
        
        # Check dependencies
        deps = envelope['deps']
        assert len(deps) == 2, "Should have two dependencies"
        assert 'identity:identity_xyz789' in deps, "Should depend on identity"
        assert 'channel:channel_abc123' in deps, "Should depend on channel"
        
        print("✓ create_message dependencies test passed")
    
    def test_create_message_empty_content(self):
        """Test that create_message handles empty content."""
        params = {
            'content': '',
            'channel_id': 'test_channel',
            'identity_id': 'test_identity'
        }
        
        envelope = create_message(params)
        
        # Should still create a valid message with empty content
        event = envelope['event_plaintext']
        assert event['content'] == ''
        assert event['type'] == 'message'
        
        print("✓ create_message empty content test passed")


def run_tests():
    """Run all message command tests."""
    test = TestMessageCommands()
    
    print("=" * 60)
    print("Testing Message Commands")
    print("=" * 60)
    
    print("\n1. Testing create_message envelope structure:")
    print("-" * 40)
    test.test_create_message_envelope_structure()
    
    print("\n2. Testing create_message dependencies:")
    print("-" * 40)
    test.test_create_message_dependencies()
    
    print("\n3. Testing create_message empty content:")
    print("-" * 40)
    test.test_create_message_empty_content()
    
    print("\n" + "=" * 60)
    print("Message command tests complete!")


if __name__ == "__main__":
    run_tests()
