"""
Tests for address commands.
"""
import pytest
from protocols.quiet.events.address.commands import announce_address
from protocols.quiet.tests.test_commands_base import CommandTestBase


class TestAddressCommands(CommandTestBase):
    """Test address commands."""
    
    def test_announce_address_envelope_structure(self):
        """Test that announce_address generates correct envelope structure."""
        params = {
            'peer_id': 'test_peer_id',
            'user_id': 'test_user_id',
            'address': '192.168.1.100',
            'port': 8080,
            'network_id': 'test_network'
        }
        
        envelope = announce_address(params)
        
        # Check envelope structure
        assert envelope['event_type'] == 'address'
        assert envelope['self_created'] == True
        assert envelope['peer_id'] == 'test_peer_id'  # Signed by this peer
        assert envelope['network_id'] == 'test_network'
        assert 'peer:test_peer_id' in envelope['deps']
        assert 'user:test_user_id' in envelope['deps']
        
        # Check event structure
        event = envelope['event_plaintext']
        assert event['type'] == 'address'
        assert event['peer_id'] == 'test_peer_id'
        assert event['user_id'] == 'test_user_id'
        assert event['address'] == '192.168.1.100'
        assert event['port'] == 8080
        assert event['network_id'] == 'test_network'
        assert 'timestamp' in event
        assert event['signature'] == ''  # Not signed yet
        
        print("✓ announce_address envelope structure test passed")
    
    def test_announce_address_ephemeral_nature(self):
        """Test that address events are ephemeral (have timestamps)."""
        params = {
            'peer_id': 'peer_123',
            'user_id': 'user_456',
            'address': '10.0.0.1',
            'port': 9000,
            'network_id': 'test_network'
        }
        
        envelope1 = announce_address(params)
        import time
        time.sleep(0.01)  # Small delay
        envelope2 = announce_address(params)
        
        # Timestamps should be different (ephemeral nature)
        ts1 = envelope1['event_plaintext']['timestamp']
        ts2 = envelope2['event_plaintext']['timestamp']
        assert ts2 > ts1, "Timestamps should increase"
        
        print("✓ announce_address ephemeral nature test passed")


def run_tests():
    """Run all address command tests."""
    test = TestAddressCommands()
    
    print("=" * 60)
    print("Testing Address Commands")
    print("=" * 60)
    
    print("\n1. Testing announce_address envelope structure:")
    print("-" * 40)
    test.test_announce_address_envelope_structure()
    
    print("\n2. Testing announce_address ephemeral nature:")
    print("-" * 40)
    test.test_announce_address_ephemeral_nature()
    
    print("\n" + "=" * 60)
    print("Address command tests complete!")


if __name__ == "__main__":
    run_tests()
