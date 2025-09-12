"""
Tests for transit_secret event type projector.
"""
import pytest
import sys
from pathlib import Path

# Add project root to path
test_dir = Path(__file__).parent
protocol_dir = test_dir.parent.parent.parent.parent
project_root = protocol_dir.parent.parent
sys.path.insert(0, str(project_root))

from protocols.quiet.events.transit_secret.projector import project


class TestTransitSecretProjector:
    """Test transit secret event projection."""
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_project_transit_secret_creates_deltas(self, sample_transit_secret_event):
        """Test that projecting transit secret creates correct deltas."""
        envelope = {
            'event_plaintext': sample_transit_secret_event,
            'event_type': 'transit_secret',
            'event_id': 'test_event_id',
            'peer_id': sample_transit_secret_event.get('created_by', sample_transit_secret_event.get('peer_id', 'test_peer_id')),
            'sig_checked': True,
            'validated': True
            }
        deltas = project(envelope)
        
        # Should return deltas
        assert isinstance(deltas, list)
        assert len(deltas) == 1
        
        # Check peer_transit_keys delta
        delta = deltas[0]
        assert delta['op'] == 'insert'
        assert delta['table'] == 'peer_transit_keys'
        assert delta['data']['transit_key_id'] == sample_transit_secret_event['transit_key_id']
        assert delta['data']['peer_id'] == sample_transit_secret_event['peer_id']
        assert delta['data']['network_id'] == sample_transit_secret_event['network_id']
        assert delta['data']['created_at'] == sample_transit_secret_event['created_at']
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_project_transit_secret_delta_structure(self, sample_transit_secret_event):
        """Test that deltas have correct structure."""
        envelope = {
            'event_plaintext': sample_transit_secret_event,
            'event_type': 'transit_secret',
            'event_id': 'test_event_id',
            'peer_id': sample_transit_secret_event.get('created_by', sample_transit_secret_event.get('peer_id', 'test_peer_id')),
            'sig_checked': True,
            'validated': True
            }
        deltas = project(envelope)
        
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
    def test_project_transit_secret_no_secret_in_delta(self, sample_transit_secret_event):
        """Test that delta doesn't include the actual secret."""
        envelope = {
            'event_plaintext': sample_transit_secret_event,
            'event_type': 'transit_secret',
            'event_id': 'test_event_id',
            'peer_id': sample_transit_secret_event.get('created_by', sample_transit_secret_event.get('peer_id', 'test_peer_id')),
            'sig_checked': True,
            'validated': True
            }
        deltas = project(envelope)
        
        # The delta should not contain the secret
        delta = deltas[0]
        assert 'secret' not in delta['data']
        assert 'encrypted_secret' not in delta['data']
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_project_transit_secret_required_fields(self, sample_transit_secret_event):
        """Test that all required fields are in the delta."""
        envelope = {
            'event_plaintext': sample_transit_secret_event,
            'event_type': 'transit_secret',
            'event_id': 'test_event_id',
            'peer_id': sample_transit_secret_event.get('created_by', sample_transit_secret_event.get('peer_id', 'test_peer_id')),
            'sig_checked': True,
            'validated': True
            }
        deltas = project(envelope)
        
        delta = deltas[0]
        required_fields = ['transit_key_id', 'peer_id', 'network_id', 'created_at']
        
        for field in required_fields:
            assert field in delta['data']
            assert delta['data'][field] is not None