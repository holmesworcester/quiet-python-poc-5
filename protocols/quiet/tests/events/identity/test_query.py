"""
Tests for identity event type query (list).
"""
import pytest
import sys
from pathlib import Path

# Add project root to path
test_dir = Path(__file__).parent
protocol_dir = test_dir.parent.parent.parent.parent
project_root = protocol_dir.parent.parent
sys.path.insert(0, str(project_root))

from protocols.quiet.events.identity.queries import get as get_identities
from protocols.quiet.events.identity.commands import create_identity


class TestIdentityQuery:
    """Test identity list query."""
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_list_empty_identities(self, initialized_db):
        """Test listing identities when none exist."""
        result = get_identities(initialized_db, {})
        assert result == []
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_list_single_identity(self, initialized_db):
        """Test listing a single identity."""
        # Create an identity
        params = {"network_id": "test-network"}
        envelope = create_identity(params)
        created_event = envelope["event_plaintext"]
        
        # List identities
        result = get_identities(initialized_db, {})
        
        assert len(result) == 1
        assert result[0]["identity_id"] == created_event["peer_id"]
        assert result[0]["network_id"] == "test-network"
        assert result[0]["created_at"] == created_event["created_at"]
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_list_multiple_identities(self, initialized_db):
        """Test listing multiple identities."""
        # Create three identities
        identities = []
        for i in range(3):
            params = {"network_id": f"network-{i}"}
            envelope = create_identity(params)
            identities.append(envelope["event_plaintext"])
        
        # List all identities
        result = get_identities(initialized_db, {})
        
        assert len(result) == 3
        
        # Check they're ordered by created_at DESC
        for i in range(len(result) - 1):
            assert result[i]["created_at"] >= result[i + 1]["created_at"]
        
        # Check all identities are present
        result_ids = {r["identity_id"] for r in result}
        created_ids = {i["peer_id"] for i in identities}
        assert result_ids == created_ids
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_list_identities_hex_conversion(self, initialized_db):
        """Test that binary peer_ids are converted to hex strings."""
        # Create an identity
        params = {"network_id": "test-network"}
        envelope = create_identity(params)
        peer_id = envelope["event_plaintext"]["peer_id"]
        
        # List identities
        result = get_identities(initialized_db, {})
        
        # Verify the identity_id is a hex string
        assert len(result) == 1
        assert isinstance(result[0]["identity_id"], str)
        assert result[0]["identity_id"] == peer_id
        
        # Should be valid hex
        bytes.fromhex(result[0]["identity_id"])  # Should not raise
    
    @pytest.mark.unit
    @pytest.mark.event_type
    def test_list_identities_fields(self, initialized_db):
        """Test that list returns only the expected fields."""
        # Create an identity
        params = {"network_id": "test-network"}
        create_identity(params)
        
        # List identities
        result = get_identities(initialized_db, {})
        
        assert len(result) == 1
        identity = result[0]
        
        # Should have exactly these fields
        expected_fields = {"identity_id", "network_id", "created_at"}
        assert set(identity.keys()) == expected_fields
        
        # Should NOT include private_key or public_key
        assert "private_key" not in identity
        assert "public_key" not in identity