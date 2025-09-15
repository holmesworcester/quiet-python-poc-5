"""
Tests for project handler.
"""
import pytest
import sys
from pathlib import Path
from typing import Dict, Any

# Add project root to path
protocol_dir = Path(__file__).parent.parent.parent
project_root = protocol_dir.parent.parent
sys.path.insert(0, str(project_root))

from protocols.quiet.handlers.project import ProjectHandler


class TestProjectHandler:
    """Test projection handler."""
    
    @pytest.fixture
    def handler(self):
        """Create handler instance."""
        return ProjectHandler()
    
    @pytest.mark.unit
    @pytest.mark.handler
    def test_filter_requires_validated(self, handler):
        """Test filter requires validated to be true."""
        envelope: Dict[str, Any] = {
            "event_type": "identity",
            "event_plaintext": {"type": "identity"}
        }
        assert handler.filter(envelope) == False
        
        envelope["validated"] = False
        assert handler.filter(envelope) == False
        
        envelope["validated"] = True
        assert handler.filter(envelope) == True
    
    @pytest.mark.unit
    @pytest.mark.handler
    def test_filter_skips_projected(self, handler):
        """Test filter skips already projected envelopes."""
        envelope: Dict[str, Any] = {
            "event_type": "identity",
            "event_plaintext": {"type": "identity"},
            "validated": True,
            "projected": True
        }
        assert handler.filter(envelope) == False
    
    @pytest.mark.unit
    @pytest.mark.handler
    def test_process_identity_event(self, handler, sample_identity_event, initialized_db):
        """Test projecting identity event."""
        envelope = {
            "event_plaintext": sample_identity_event,
            "event_type": "identity",
            "validated": True,
            "peer_id": sample_identity_event["peer_id"],
            "network_id": sample_identity_event["network_id"]
        }
        
        results = handler.process(envelope, initialized_db)
        
        assert len(results) == 1
        result = results[0]
        
        # Should mark as projected
        assert result["projected"] == True
        
        # Check database for projected data
        cursor = initialized_db.cursor()
        cursor.execute(
            "SELECT * FROM peer_identities WHERE peer_id = ?",
            (sample_identity_event["peer_id"],)
        )
        
        row = cursor.fetchone()
        assert row is not None
    
    @pytest.mark.unit
    @pytest.mark.handler
    def test_process_key_event(self, handler, sample_key_event, initialized_db):
        """Test projecting key event."""
        envelope = {
            "event_plaintext": sample_key_event,
            "event_type": "key",
            "validated": True
        }
        
        results = handler.process(envelope, initialized_db)
        
        assert len(results) == 1
        result = results[0]
        
        # Should mark as projected
        assert result["projected"] == True
    
    @pytest.mark.unit
    @pytest.mark.handler
    def test_process_transit_secret_event(self, handler, sample_transit_secret_event, initialized_db):
        """Test projecting transit secret event."""
        envelope = {
            "event_plaintext": sample_transit_secret_event,
            "event_type": "transit_secret",
            "validated": True
        }
        
        results = handler.process(envelope, initialized_db)
        
        assert len(results) == 1
        result = results[0]
        
        # Should mark as projected
        assert result["projected"] == True
    
    @pytest.mark.unit
    @pytest.mark.handler
    def test_process_unknown_event_type(self, handler, initialized_db):
        """Test projecting unknown event type."""
        envelope = {
            "event_plaintext": {"type": "unknown"},
            "event_type": "unknown",
            "validated": True
        }
        
        results = handler.process(envelope, initialized_db)
        
        assert len(results) == 1
        result = results[0]
        
        # Should still return envelope but without projected flag
        # (no projector for unknown type)
        assert result.get("projected") != True
    
    @pytest.mark.unit
    @pytest.mark.handler
    def test_process_preserves_envelope(self, handler, sample_identity_event, initialized_db):
        """Test that handler preserves envelope data."""
        envelope = {
            "event_plaintext": sample_identity_event,
            "event_type": "identity",
            "validated": True,
            "custom_field": "preserved",
            "peer_id": sample_identity_event["peer_id"],
            "network_id": sample_identity_event["network_id"]
        }
        
        results = handler.process(envelope, initialized_db)
        result = results[0]
        
        # All fields should be preserved
        assert result["event_plaintext"] == sample_identity_event
        assert result["event_type"] == "identity"
        assert result["validated"] == True
        assert result["custom_field"] == "preserved"
        assert result["projected"] == True