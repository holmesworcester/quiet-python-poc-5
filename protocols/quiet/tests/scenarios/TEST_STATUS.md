# Scenario Tests Status

## Overview
The scenario tests have been created for the Quiet protocol following the patterns from poc-3/protocols/signed_groups, but using real Python API calls instead of JSON-based test definitions.

## Test Structure Created

### Test Files
1. **`base.py`** - Base test class with pytest (requires pytest installation)
2. **`base_simple.py`** - Base test class without pytest dependency
3. **`test_basic_flows.py`** - Tests for basic protocol operations
4. **`test_multi_user_flows.py`** - Tests for multi-user interactions
5. **`test_edge_cases.py`** - Tests for edge cases and error handling
6. **`conftest.py`** - Pytest configuration
7. **`README.md`** - Documentation

### Test Coverage
The tests cover:
- Identity creation and management
- Key creation (event-layer encryption)
- Transit secret creation (transit-layer encryption)
- Multi-user scenarios with event sharing
- Event dependency resolution
- Network isolation
- Error handling and edge cases
- Database persistence
- Concurrent operations

## Running the Tests

### Requirements
The tests require the following Python packages to be installed:
```bash
pip install -r requirements.txt
```

Required packages:
- PyYAML (for OpenAPI spec parsing)
- pytest (for test framework)
- PyNaCl (for cryptography)

### Running with pytest
```bash
# Run all scenario tests
pytest protocols/quiet/tests/scenarios/

# Run specific test file
pytest protocols/quiet/tests/scenarios/test_basic_flows.py -v

# Run specific test
pytest protocols/quiet/tests/scenarios/test_basic_flows.py::TestBasicFlows::test_identity_creation -v
```

### Alternative: Standalone Test Runner
A standalone test runner is also provided at the project root:
```bash
python3 test_scenarios.py
```

This requires the same dependencies but doesn't use pytest.

## Current Status
The tests are **ready to run** but require the Python dependencies to be installed first. The test structure matches the poc-3 patterns but uses:
- Real API calls through `APIClient`
- Direct function execution instead of HTTP
- Python assertions instead of JSON-based assertions
- Actual database state verification

## Key Differences from poc-3
1. **Real API Calls**: Tests use the actual `APIClient` class to make API calls
2. **Direct Execution**: No HTTP server needed - functions are called directly
3. **Database Isolation**: Each test client gets its own database
4. **Event Sharing**: `share_event()` method simulates network propagation
5. **Python Native**: Uses Python test patterns instead of JSON test definitions

## Next Steps
1. Install required dependencies: `pip install -r requirements.txt`
2. Run the tests to verify they pass
3. Add more scenario tests as needed
4. Consider adding performance/load tests