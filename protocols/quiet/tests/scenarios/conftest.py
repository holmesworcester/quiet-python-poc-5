"""
Pytest configuration for scenario tests.
"""
import pytest
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Add protocol root to Python path
protocol_root = Path(__file__).parent.parent.parent
if str(protocol_root) not in sys.path:
    sys.path.insert(0, str(protocol_root))


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers",
        "scenario: mark test as a scenario test"
    )
    config.addinivalue_line(
        "markers", 
        "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers",
        "multi_user: mark test as multi-user scenario"
    )


@pytest.fixture(autouse=True)
def mark_scenario_tests(request):
    """Automatically mark all tests in scenarios directory as scenario tests."""
    request.node.add_marker(pytest.mark.scenario)