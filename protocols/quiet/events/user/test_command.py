"""
Tests for user commands.
"""
import pytest
import base64
import json
from protocols.quiet.events.user.commands import join_as_user, create_user
from protocols.quiet.tests.test_commands_base import CommandTestBase


class TestUserCommands(CommandTestBase):
    """Test user commands."""
    
    def test_join_as_user_envelope_structure(self):
        """Test that join_as_user generates correct envelope structure."""
        # Create a test invite link
        invite_data = {
            'invite_secret': 'test_secret_123',
            'network_id': 'test_network',
            'group_id': 'test_group'
        }
        invite_json = json.dumps(invite_data)
        invite_b64 = base64.b64encode(invite_json.encode()).decode()
        invite_link = f"quiet://invite/{invite_b64}"
        
        params = {
            'invite_link': invite_link,
            'name': 'Alice'
        }
        
        envelopes = join_as_user(params)
        
        # Should return 3 envelopes: identity, peer, user
        assert len(envelopes) == 3, "Should create 3 envelopes"
        
        # Check identity envelope
        identity_env = envelopes[0]
        assert identity_env['event_type'] == 'identity'
        assert identity_env['self_created'] == True
        assert identity_env['validated'] == True
        assert 'secret' in identity_env
        identity_event = identity_env['event_plaintext']
        assert identity_event['type'] == 'identity'
        assert identity_event['name'] == 'Alice'
        assert 'public_key' in identity_event
        
        # Check peer envelope
        peer_env = envelopes[1]
        assert peer_env['event_type'] == 'peer'
        assert peer_env['self_created'] == True
        peer_event = peer_env['event_plaintext']
        assert peer_event['type'] == 'peer'
        assert 'public_key' in peer_event
        assert 'identity_id' in peer_event
        
        # Check user envelope
        user_env = envelopes[2]
        assert user_env['event_type'] == 'user'
        assert user_env['self_created'] == True
        user_event = user_env['event_plaintext']
        assert user_event['type'] == 'user'
        assert user_event['peer_id'] == '@generated:peer:0'  # Placeholder
        assert user_event['name'] == 'Alice'
        assert user_event['group_id'] == 'test_group'
        assert 'invite_pubkey' in user_event
        assert 'invite_signature' in user_event
        
        print("✓ join_as_user envelope structure test passed")
    
    def test_join_as_user_placeholder_resolution(self):
        """Test that join_as_user uses placeholders correctly."""
        invite_data = {
            'invite_secret': 'test_secret',
            'network_id': 'test_network',
            'group_id': 'test_group'
        }
        invite_json = json.dumps(invite_data)
        invite_b64 = base64.b64encode(invite_json.encode()).decode()
        invite_link = f"quiet://invite/{invite_b64}"
        
        params = {
            'invite_link': invite_link,
            'name': 'Bob'
        }
        
        envelopes = join_as_user(params)
        
        # Check that user event references peer with placeholder
        user_env = envelopes[2]
        user_event = user_env['event_plaintext']
        assert user_event['peer_id'] == '@generated:peer:0'
        
        # Check that user deps include placeholder
        assert '@generated:peer:0' in user_env['deps']
        
        print("✓ join_as_user placeholder resolution test passed")
    
    def test_create_user_envelope_structure(self):
        """Test that create_user generates correct envelope structure."""
        params = {
            'identity_id': 'test_identity_id',
            'network_id': 'test_network',
            'address': '192.168.1.100',
            'port': 8080
        }
        
        envelope = create_user(params)
        
        # Check envelope structure
        assert envelope['event_type'] == 'user'
        assert envelope['self_created'] == True
        assert envelope['peer_id'] == 'test_identity_id'
        assert envelope['network_id'] == 'test_network'
        assert envelope['deps'] == ['identity:test_identity_id']
        
        # Check event structure
        event = envelope['event_plaintext']
        assert event['type'] == 'user'
        assert event['peer_id'] == 'test_identity_id'
        assert event['network_id'] == 'test_network'
        assert event['address'] == '192.168.1.100'
        assert event['port'] == 8080
        assert 'created_at' in event
        assert event['signature'] == ''  # Not signed yet
        
        print("✓ create_user envelope structure test passed")


def run_tests():
    """Run all user command tests."""
    test = TestUserCommands()
    
    print("=" * 60)
    print("Testing User Commands")
    print("=" * 60)
    
    print("\n1. Testing join_as_user envelope structure:")
    print("-" * 40)
    test.test_join_as_user_envelope_structure()
    
    print("\n2. Testing join_as_user placeholder resolution:")
    print("-" * 40)
    test.test_join_as_user_placeholder_resolution()
    
    print("\n3. Testing create_user envelope structure:")
    print("-" * 40)
    test.test_create_user_envelope_structure()
    
    print("\n" + "=" * 60)
    print("User command tests complete!")


if __name__ == "__main__":
    run_tests()
