#!/usr/bin/env python3
"""
Simple test to verify the scenario tests work without pytest.
"""
import sys
from pathlib import Path

# Add paths
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Now we can import after adding to path
from protocols.quiet.tests.scenarios.base_simple import ScenarioTestBase

class SimpleTest(ScenarioTestBase):
    def test_identity_creation(self):
        """Test creating an identity through the API."""
        # Create client
        alice = self.create_client("alice")
        
        # Create identity
        identity = alice.create_identity("test-network")
        
        # Verify identity was created
        assert identity["identity_id"] is not None
        assert identity["network_id"] == "test-network"
        assert identity["created_at"] is not None
        
        # Verify identity appears in list
        identities = alice.get_identities()
        assert len(identities) == 1
        assert identities[0]["peer_id"] == identity["identity_id"]
        
        print("✓ Identity creation test passed")

if __name__ == "__main__":
    test = SimpleTest()
    test.setup_method(None)
    try:
        test.test_identity_creation()
        print("\nAll tests passed!")
    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        test.teardown_method(None)