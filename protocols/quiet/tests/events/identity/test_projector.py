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
    def test_project_identity_creates_deltas(self, sample_identity_event):
        """Test that projecting identity creates correct deltas."""
        # Wrap the event in an envelope as projectors expect
        envelope = {
            'event_plaintext': sample_identity_event,
            'event_type': 'identity',
            'event_id': 'test_event_id',
            'peer_id': sample_identity_event['peer_id'],
            'self_created': True,
            'sig_checked': True,
            'validated': True
        }
        deltas = project(envelope)
        
        # Should return deltas
        assert isinstance(deltas, list)
        assert len(deltas) > 0
        
        # Check for peer creation delta (no user creation anymore)
        peer_deltas = [d for d in deltas if d.get('table') == 'peers']
        assert len(peer_deltas) == 1
        
        peer_delta = peer_deltas[0]
        assert peer_delta['op'] == 'insert'
        assert peer_delta['data']['peer_id'] == sample_identity_event['peer_id']
        assert peer_delta['data']['network_id'] == sample_identity_event['network_id']
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_project_identity_delta_structure(self, sample_identity_event):
        """Test that deltas have correct structure."""
        envelope = {
            'event_plaintext': sample_identity_event,
            'event_type': 'identity',
            'event_id': 'test_event_id',
            'peer_id': sample_identity_event['peer_id'],
            'self_created': True,
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
    def test_project_identity_peer_public_key(self, sample_identity_event):
        """Test that peer delta includes public key as bytes."""
        envelope = {
            'event_plaintext': sample_identity_event,
            'event_type': 'identity',
            'event_id': 'test_event_id',
            'peer_id': sample_identity_event['peer_id'],
            'self_created': True,
            'sig_checked': True,
            'validated': True
        }
        deltas = project(envelope)
        
        peer_delta = next(d for d in deltas if d['table'] == 'peers')
        assert 'public_key' in peer_delta['data']
        
        # Should be bytes
        assert isinstance(peer_delta['data']['public_key'], bytes)
        
        # Should match peer_id when decoded
        assert peer_delta['data']['public_key'].hex() == sample_identity_event['peer_id']
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_project_identity_created_at(self, sample_identity_event):
        """Test that peer delta includes created_at timestamp."""
        envelope = {
            'event_plaintext': sample_identity_event,
            'event_type': 'identity',
            'event_id': 'test_event_id',
            'peer_id': sample_identity_event['peer_id'],
            'self_created': True,
            'sig_checked': True,
            'validated': True
        }
        deltas = project(envelope)
        
        peer_delta = next(d for d in deltas if d['table'] == 'peers')
        assert peer_delta['data']['added_at'] == sample_identity_event['created_at']
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_project_identity_with_secret(self, sample_identity_event):
        """Test that identity projector creates identities table entry when secret is present."""
        envelope = {
            'event_plaintext': sample_identity_event,
            'event_type': 'identity',
            'event_id': 'test_event_id',
            'peer_id': sample_identity_event['peer_id'],
            'self_created': True,
            'sig_checked': True,
            'validated': True,
            'secret': {
                'private_key': 'test_private_key_hex',
                'public_key': 'test_public_key_hex'
            }
        }
        deltas = project(envelope)
        
        # Should create identities table entry when secret is present
        identity_deltas = [d for d in deltas if d.get('table') == 'identities']
        assert len(identity_deltas) == 1
        
        identity_delta = identity_deltas[0]
        assert identity_delta['op'] == 'insert'
        assert identity_delta['data']['identity_id'] == sample_identity_event['peer_id']
        assert identity_delta['data']['private_key'] == 'test_private_key_hex'
        assert identity_delta['data']['public_key'] == 'test_public_key_hex'