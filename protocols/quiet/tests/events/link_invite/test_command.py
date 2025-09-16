"""
Tests for link_invite commands.
"""
import pytest
from protocols.quiet.events.link_invite.commands import create_link_invite
from protocols.quiet.tests.test_commands_base import CommandTestBase


class TestLinkInviteCommands(CommandTestBase):
    """Test link_invite commands."""
    
    def test_create_link_invite_envelope_structure(self):
        """Test that create_link_invite generates correct envelope structure."""
        params = {
            'peer_id': 'test_peer_id_hash',
            'user_id': 'test_user_id_hash',
            'network_id': 'test_network'
        }
        
        envelope = create_link_invite(params)
        
        # Check envelope structure
        assert envelope['event_type'] == 'link_invite'
        assert envelope['self_created'] == True
        assert envelope['peer_id'] == 'test_peer_id_hash'  # Signed by the peer
        assert envelope['network_id'] == 'test_network'
        assert 'peer:test_peer_id_hash' in envelope['deps']
        assert 'user:test_user_id_hash' in envelope['deps']
        
        # Check event structure
        event = envelope['event_plaintext']
        assert event['type'] == 'link_invite'
        assert event['peer_id'] == 'test_peer_id_hash'
        assert event['user_id'] == 'test_user_id_hash'
        assert event['network_id'] == 'test_network'
        assert 'created_at' in event
        assert event['signature'] == ''  # Not signed yet
        
        print("✓ create_link_invite envelope structure test passed")
    
    def test_create_link_invite_with_dependencies(self):
        """Test link_invite creation with proper dependencies."""
        # This would need a full setup with peer and user events
        # For now, just test the envelope structure
        
        params = {
            'peer_id': 'peer_abc123',
            'user_id': 'user_xyz789',
            'network_id': 'test_network'
        }
        
        envelope = create_link_invite(params)
        
        # Check dependencies are properly set
        deps = envelope['deps']
        assert len(deps) == 2, "Should have two dependencies"
        assert 'peer:peer_abc123' in deps, "Should depend on peer"
        assert 'user:user_xyz789' in deps, "Should depend on user"
        
        print("✓ create_link_invite dependency test passed")


def run_tests():
    """Run all link_invite command tests."""
    test = TestLinkInviteCommands()
    
    print("=" * 60)
    print("Testing Link Invite Commands")
    print("=" * 60)
    
    print("\n1. Testing create_link_invite envelope structure:")
    print("-" * 40)
    test.test_create_link_invite_envelope_structure()
    
    print("\n2. Testing create_link_invite with dependencies:")
    print("-" * 40)
    test.test_create_link_invite_with_dependencies()
    
    print("\n" + "=" * 60)
    print("Link invite command tests complete!")


if __name__ == "__main__":
    run_tests()
