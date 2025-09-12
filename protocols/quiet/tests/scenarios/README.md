# Quiet Protocol Scenario Tests

This directory contains scenario tests for the Quiet protocol that use real API calls to test end-to-end functionality.

## Structure

- `base.py` - Base class with utilities for scenario tests
- `test_basic_flows.py` - Basic protocol operations (identity, key creation)
- `test_multi_user_flows.py` - Multi-user interactions and event sharing
- `test_edge_cases.py` - Edge cases and error conditions

## Running Tests

Run all scenario tests:
```bash
pytest protocols/quiet/tests/scenarios/
```

Run specific test file:
```bash
pytest protocols/quiet/tests/scenarios/test_basic_flows.py
```

Run with verbose output:
```bash
pytest -v protocols/quiet/tests/scenarios/
```

## Test Features

### Base Test Class

The `ScenarioTestBase` class provides:
- Isolated test environments with separate databases
- Multiple named API clients
- Event sharing between clients
- Database state assertions
- Automatic cleanup

### Test Categories

1. **Basic Flows** - Fundamental protocol operations:
   - Identity creation
   - Key management
   - Transit secret creation
   - Database operations

2. **Multi-User Flows** - Interactions between multiple clients:
   - Key distribution
   - Transit secret exchange
   - Event dependencies
   - Network isolation

3. **Edge Cases** - Error handling and boundary conditions:
   - Invalid parameters
   - Malformed events
   - Concurrent operations
   - Database persistence

## Writing New Tests

1. Create a new test class inheriting from `ScenarioTestBase`
2. Use `create_client()` to create named clients
3. Use API methods to perform operations
4. Use `share_event()` to simulate network communication
5. Use assertion methods to verify state

Example:
```python
class TestNewScenario(ScenarioTestBase):
    def test_my_scenario(self):
        # Create clients
        alice = self.create_client("alice")
        bob = self.create_client("bob")
        
        # Perform operations
        alice_id = alice.create_identity("test-network")
        
        # Share events
        self.share_event("alice", "bob", event_data)
        
        # Assert results
        self.assert_event_exists("bob", "identity", peer_id=alice_id["identity_id"])
```