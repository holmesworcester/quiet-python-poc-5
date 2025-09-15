"""
Tests for identity commands.
"""
import pytest
from protocols.quiet.tests.test_commands_base import CommandTestBase


class TestIdentityCommands(CommandTestBase):
    """Test identity commands."""
    
    def test_create_identity_envelope_structure(self):
        """Test that create_identity generates correct envelope structure."""
        # Import the command
        from protocols.quiet.events.identity.commands import create_identity
        
        params = {
            'name': 'Alice',
            'network_id': 'test_network'
        }
        
        envelope = create_identity(params)
        
        # Check envelope structure
        assert envelope['event_type'] == 'identity'
        assert envelope['self_created'] == True
        assert envelope['validated'] == True  # Pre-validated (local-only)
        assert 'event_id' in envelope  # Pre-calculated hash
        assert envelope['network_id'] == 'test_network'
        assert envelope['deps'] == []  # No dependencies
        assert envelope['deps_included_and_valid'] == True
        assert 'secret' in envelope  # Contains private key
        
        # Check event structure
        event = envelope['event_plaintext']
        assert event['type'] == 'identity'
        assert event['name'] == 'Alice'
        assert event['network_id'] == 'test_network'
        assert 'public_key' in event
        assert 'created_at' in event
        # No signature field for identity events (local-only)
        
        # Check secret structure
        secret = envelope['secret']
        assert 'private_key' in secret
        assert 'public_key' in secret
        assert len(secret['private_key']) == 64  # Hex encoded
        assert len(secret['public_key']) == 64
        
        print("✓ create_identity envelope structure test passed")
    
    def test_create_identity_api_response(self):
        """Test that create_identity works through the pipeline."""
        from protocols.quiet.events.identity.commands import create_identity
        
        params = {
            'name': 'Bob',
            'network_id': 'test_network'
        }
        
        result = self.run_command('create_identity', params)
        
        # Identity should always be stored (local-only, no deps)
        assert 'identity' in result, "Identity should be stored"
        assert len(result['identity']) == 32, "Identity ID should be 32 hex chars"
        
        print(f"✓ Identity stored with ID: {result['identity']}")
        print("✓ create_identity API response test passed")


def run_tests():
    """Run all identity command tests."""
    test = TestIdentityCommands()
    
    print("=" * 60)
    print("Testing Identity Commands")
    print("=" * 60)
    
    print("\n1. Testing create_identity envelope structure:")
    print("-" * 40)
    test.test_create_identity_envelope_structure()
    
    print("\n2. Testing create_identity API response:")
    print("-" * 40)
    test.test_create_identity_api_response()
    
    print("\n" + "=" * 60)
    print("Identity command tests complete!")


if __name__ == "__main__":
    run_tests()
