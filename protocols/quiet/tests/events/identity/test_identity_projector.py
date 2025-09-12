"""
Tests for identity event type projector.
"""
import pytest
import sys
from pathlib import Path

# Add project root to path
test_dir = Path(__file__).parent
protocol_dir = test_dir.parent.parent.parent.parent
project_root = protocol_dir.parent.parent
sys.path.insert(0, str(project_root))

from protocols.quiet.events.identity.projector import project


class TestIdentityProjector:
    """Test identity event projection."""
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_project_identity_creates_deltas(self, sample_identity_event, initialized_db):
        """Test that projecting identity creates correct deltas."""
        deltas = project(sample_identity_event, initialized_db)
        
        # Should return deltas
        assert isinstance(deltas, list)
        assert len(deltas) > 0
        
        # Check for user creation delta
        user_deltas = [d for d in deltas if d.get('table') == 'users']
        assert len(user_deltas) == 1
        
        user_delta = user_deltas[0]
        assert user_delta['op'] == 'insert'
        assert user_delta['data']['user_id'] == sample_identity_event['peer_id']
        assert user_delta['data']['network_id'] == sample_identity_event['network_id']
        
        # Check for peer creation delta
        peer_deltas = [d for d in deltas if d.get('table') == 'peers']
        assert len(peer_deltas) == 1
        
        peer_delta = peer_deltas[0]
        assert peer_delta['op'] == 'insert'
        assert peer_delta['data']['peer_id'] == sample_identity_event['peer_id']
        assert peer_delta['data']['network_id'] == sample_identity_event['network_id']
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_project_identity_delta_structure(self, sample_identity_event, initialized_db):
        """Test that deltas have correct structure."""
        deltas = project(sample_identity_event, initialized_db)
        
        for delta in deltas:
            # Each delta must have op, table, and data
            assert 'op' in delta
            assert 'table' in delta
            assert 'data' in delta
            
            # op should be a valid operation
            assert delta['op'] in ['insert', 'update', 'delete']
            
            # data should be a dict
            assert isinstance(delta['data'], dict)
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_project_identity_peer_public_key(self, sample_identity_event, initialized_db):
        """Test that peer delta includes public key as bytes."""
        deltas = project(sample_identity_event, initialized_db)
        
        peer_delta = next(d for d in deltas if d['table'] == 'peers')
        assert 'public_key' in peer_delta['data']
        
        # Should be bytes
        assert isinstance(peer_delta['data']['public_key'], bytes)
        
        # Should match peer_id when decoded
        assert peer_delta['data']['public_key'].hex() == sample_identity_event['peer_id']
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_project_identity_created_at(self, sample_identity_event, initialized_db):
        """Test that peer delta includes created_at timestamp."""
        deltas = project(sample_identity_event, initialized_db)
        
        peer_delta = next(d for d in deltas if d['table'] == 'peers')
        assert peer_delta['data']['added_at'] == sample_identity_event['created_at']
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_project_identity_user_defaults(self, sample_identity_event, initialized_db):
        """Test that user delta includes default values."""
        deltas = project(sample_identity_event, initialized_db)
        
        user_delta = next(d for d in deltas if d['table'] == 'users')
        
        # Should have default name
        assert 'name' in user_delta['data']
        assert user_delta['data']['name'] == 'User'
        
        # Should link to peer
        assert user_delta['data']['peer_id'] == sample_identity_event['peer_id']