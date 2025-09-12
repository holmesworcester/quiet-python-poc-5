"""
Tests for user event type projector.
"""
import pytest
import sys
import time
from pathlib import Path

# Add project root to path
test_dir = Path(__file__).parent
protocol_dir = test_dir.parent.parent.parent.parent
project_root = protocol_dir.parent.parent
sys.path.insert(0, str(project_root))

from protocols.quiet.events.user.projector import project


class TestUserProjector:
    """Test user event projection."""
    
    @pytest.fixture
    def sample_user_event(self):
        """Create a sample user event envelope."""
        return {
            'event_plaintext': {
                'type': 'user',
                'user_id': 'test-user-id',
                'peer_id': 'test-peer-id',
                'network_id': 'test-network',
                'address': '192.168.1.100',
                'port': 8080,
                'created_at': int(time.time() * 1000),
                'signature': 'test-signature'
            },
            'event_type': 'user',
            'peer_id': 'test-peer-id',
            'network_id': 'test-network'
        }
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_project_user_creates_deltas(self, sample_user_event):
        """Test that projecting a user creates the right deltas."""
        deltas = project(sample_user_event)
        
        # Should create exactly one delta
        assert len(deltas) == 1
        
        delta = deltas[0]
        assert delta['op'] == 'insert'
        assert delta['table'] == 'users'
        
        # Check all fields are included
        data = delta['data']
        event_data = sample_user_event['event_plaintext']
        assert data['user_id'] == event_data['user_id']
        assert data['peer_id'] == event_data['peer_id']
        assert data['network_id'] == event_data['network_id']
        assert data['joined_at'] == event_data['created_at']
        assert data['last_address'] == event_data['address']
        assert data['last_port'] == event_data['port']
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_project_user_placeholder_address(self):
        """Test projecting user with placeholder address."""
        envelope = {
            'event_plaintext': {
                'type': 'user',
                'user_id': 'offline-user',
                'peer_id': 'offline-peer',
                'network_id': 'test-network',
                'address': '0.0.0.0',
                'port': 0,
                'created_at': int(time.time() * 1000),
                'signature': 'test-signature'
            }
        }
        
        deltas = project(envelope)
        
        # Placeholder values should be preserved
        assert deltas[0]['data']['last_address'] == '0.0.0.0'
        assert deltas[0]['data']['last_port'] == 0
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_project_user_timestamps(self, sample_user_event):
        """Test that timestamps are preserved correctly."""
        created_at = sample_user_event['event_plaintext']['created_at']
        
        deltas = project(sample_user_event)
        
        # joined_at should match created_at
        assert deltas[0]['data']['joined_at'] == created_at
    
    @pytest.mark.unit
    @pytest.mark.event_type  
    def test_project_user_delta_structure(self, sample_user_event):
        """Test the structure of the delta returned."""
        deltas = project(sample_user_event)
        
        delta = deltas[0]
        
        # Check delta has required fields
        assert 'op' in delta
        assert 'table' in delta
        assert 'data' in delta
        
        # Check operation type
        assert delta['op'] == 'insert'
        assert delta['table'] == 'users'
        
        # Data should be a dict
        assert isinstance(delta['data'], dict)
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_project_multiple_users(self):
        """Test projecting multiple different users."""
        # First user
        envelope1 = {
            'event_plaintext': {
                'type': 'user',
                'user_id': 'user-1',
                'peer_id': 'peer-1',
                'network_id': 'network-1',
                'address': '192.168.1.100',
                'port': 8080,
                'created_at': 1000,
                'signature': 'sig-1'
            }
        }
        
        # Second user
        envelope2 = {
            'event_plaintext': {
                'type': 'user',
                'user_id': 'user-2',
                'peer_id': 'peer-2',
                'network_id': 'network-1',
                'address': '192.168.1.101',
                'port': 8081,
                'created_at': 2000,
                'signature': 'sig-2'
            }
        }
        
        deltas1 = project(envelope1)
        deltas2 = project(envelope2)
        
        # Each should produce one delta
        assert len(deltas1) == 1
        assert len(deltas2) == 1
        
        # Different user IDs
        assert deltas1[0]['data']['user_id'] != deltas2[0]['data']['user_id']
        
        # Different peer IDs
        assert deltas1[0]['data']['peer_id'] != deltas2[0]['data']['peer_id']
        
        # Same network
        assert deltas1[0]['data']['network_id'] == deltas2[0]['data']['network_id']
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_project_user_ipv6_address(self):
        """Test projecting user with IPv6 address."""
        envelope = {
            'event_plaintext': {
                'type': 'user',
                'user_id': 'ipv6-user',
                'peer_id': 'ipv6-peer',
                'network_id': 'test-network',
                'address': '2001:0db8:85a3:0000:0000:8a2e:0370:7334',
                'port': 8080,
                'created_at': int(time.time() * 1000),
                'signature': 'test-signature'
            }
        }
        
        deltas = project(envelope)
        
        # IPv6 address should be preserved
        assert deltas[0]['data']['last_address'] == '2001:0db8:85a3:0000:0000:8a2e:0370:7334'
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_project_user_no_extra_fields(self, sample_user_event):
        """Test that only expected fields are included in projection."""
        deltas = project(sample_user_event)
        
        data = deltas[0]['data']
        
        # Check only expected fields are present
        expected_fields = {
            'user_id', 'peer_id', 'network_id', 
            'joined_at', 'last_address', 'last_port'
        }
        
        assert set(data.keys()) == expected_fields
        
        # Signature should not be included in projection
        assert 'signature' not in data
        assert 'created_at' not in data  # Should be joined_at instead