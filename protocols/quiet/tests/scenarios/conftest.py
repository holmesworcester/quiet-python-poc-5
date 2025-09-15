"""
Pytest configuration and fixtures for scenario tests.

Provides fixtures for single-database multi-identity testing, reflecting the real
architecture where a single client manages multiple identities that communicate
via loopback.
"""
import pytest
import sqlite3
import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from core.pipeline import PipelineRunner

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


# ============================================================================
# Single Database Test Fixtures
# ============================================================================

class ScenarioTestContext:
    """Context object for scenario tests with helper methods."""

    def __init__(self, db: sqlite3.Connection, pipeline: PipelineRunner):
        self.db = db
        self.pipeline = pipeline
        self.identities: Dict[str, str] = {}  # name -> identity_id
        self.networks: Dict[str, str] = {}    # name -> network_id
        self.channels: Dict[str, str] = {}    # name -> channel_id
        self.groups: Dict[str, str] = {}      # name -> group_id

    def create_identity(self, name: str) -> str:
        """Create an identity and return its ID."""
        result = self.pipeline.run(
            protocol_dir='protocols/quiet',
            db=self.db,
            commands=[{
                'name': 'create_identity',
                'params': {'name': name}
            }]
        )

        if result and 'identity' in result:
            identity_id = result['identity']
            self.identities[name] = identity_id
            return identity_id

        raise ValueError(f"Failed to create identity for {name}")

    def create_network(self, creator_name: str, network_name: str, username: str = None) -> str:
        """Create a network with an existing identity."""
        identity_id = self.identities.get(creator_name)
        if not identity_id:
            raise ValueError(f"Identity {creator_name} not found")

        params = {
            'name': network_name,
            'identity_id': identity_id
        }
        if username:
            params['username'] = username

        result = self.pipeline.run(
            protocol_dir='protocols/quiet',
            db=self.db,
            commands=[{
                'name': 'create_network',
                'params': params
            }]
        )

        if result and 'network' in result:
            network_id = result['network']
            self.networks[network_name] = network_id
            return network_id

        raise ValueError(f"Failed to create network {network_name}")

    def create_group(self, creator_name: str, group_name: str, network_name: str) -> str:
        """Create a group in a network."""
        identity_id = self.identities.get(creator_name)
        network_id = self.networks.get(network_name)

        if not identity_id or not network_id:
            raise ValueError("Identity or network not found")

        result = self.pipeline.run(
            protocol_dir='protocols/quiet',
            db=self.db,
            commands=[{
                'name': 'create_group',
                'params': {
                    'name': group_name,
                    'network_id': network_id,
                    'identity_id': identity_id
                }
            }]
        )

        if result and 'group' in result:
            group_id = result['group']
            self.groups[group_name] = group_id
            return group_id

        raise ValueError(f"Failed to create group {group_name}")

    def create_channel(self, creator_name: str, channel_name: str,
                      group_name: str, network_name: str) -> str:
        """Create a channel in a group."""
        identity_id = self.identities.get(creator_name)
        group_id = self.groups.get(group_name)
        network_id = self.networks.get(network_name)

        if not all([identity_id, group_id, network_id]):
            raise ValueError("Identity, group, or network not found")

        result = self.pipeline.run(
            protocol_dir='protocols/quiet',
            db=self.db,
            commands=[{
                'name': 'create_channel',
                'params': {
                    'name': channel_name,
                    'group_id': group_id,
                    'network_id': network_id,
                    'identity_id': identity_id
                }
            }]
        )

        if result and 'channel' in result:
            channel_id = result['channel']
            self.channels[channel_name] = channel_id
            return channel_id

        raise ValueError(f"Failed to create channel {channel_name}")

    def join_network(self, joiner_name: str, network_name: str, username: str = None) -> str:
        """Join a network as a user."""
        identity_id = self.identities.get(joiner_name)
        network_id = self.networks.get(network_name)

        if not identity_id or not network_id:
            raise ValueError("Identity or network not found")

        params = {
            'username': username or joiner_name,
            'network_id': network_id,
            'identity_id': identity_id
        }

        result = self.pipeline.run(
            protocol_dir='protocols/quiet',
            db=self.db,
            commands=[{
                'name': 'create_user',
                'params': params
            }]
        )

        if result and 'user' in result:
            return result['user']

        return network_id

    def send_message(self, sender_name: str, content: str, channel_name: str) -> Optional[str]:
        """Send a message to a channel."""
        identity_id = self.identities.get(sender_name)
        channel_id = self.channels.get(channel_name)

        if not identity_id or not channel_id:
            raise ValueError("Identity or channel not found")

        result = self.pipeline.run(
            protocol_dir='protocols/quiet',
            db=self.db,
            commands=[{
                'name': 'create_message',
                'params': {
                    'content': content,
                    'channel_id': channel_id,
                    'identity_id': identity_id
                }
            }]
        )

        if result and 'message' in result:
            return result['message']
        return None

    def get_messages(self, viewer_name: str, channel_name: str) -> List[Dict[str, Any]]:
        """Get messages from a channel as viewed by an identity."""
        identity_id = self.identities.get(viewer_name)
        channel_id = self.channels.get(channel_name)

        if not identity_id or not channel_id:
            return []

        # Query messages directly from database
        # In a real scenario, this would be done through API queries
        cursor = self.db.execute("""
            SELECT m.message_id, m.content, m.channel_id, m.author_id, m.created_at, u.name as author_name
            FROM messages m
            LEFT JOIN users u ON m.author_id = u.user_id
            WHERE m.channel_id = ?
            ORDER BY m.created_at ASC
        """, (channel_id,))

        messages = []
        for row in cursor:
            messages.append({
                'message_id': row[0],
                'content': row[1],
                'channel_id': row[2],
                'author_id': row[3],
                'created_at': row[4],
                'author_name': row[5] if row[5] else 'Unknown'
            })

        return messages

    def run_sync_job(self) -> None:
        """Trigger the sync job."""
        sync_job_envelope = {
            'event_type': 'run_job',
            'job_name': 'sync_request',
            'timestamp_ms': int(time.time() * 1000)
        }

        self.pipeline.run(
            protocol_dir='protocols/quiet',
            db=self.db,
            input_envelopes=[sync_job_envelope]
        )

    def simulate_sync(self, from_identity: str, to_identity: str, network_name: str) -> None:
        """Simulate a sync between two identities."""
        from_id = self.identities.get(from_identity)
        to_id = self.identities.get(to_identity)
        network_id = self.networks.get(network_name)

        if not all([from_id, to_id, network_id]):
            raise ValueError("Identity or network not found")

        # Create a sync request envelope
        sync_envelope = {
            'event_type': 'sync_request',
            'event_plaintext': {
                'type': 'sync_request',
                'request_id': 'test-sync',
                'network_id': network_id,
                'from_identity': from_id,
                'to_peer': to_id,
                'timestamp_ms': int(time.time() * 1000),
                'last_sync_ms': 0
            },
            'validated': True,
            'is_outgoing': False,
            'network_id': network_id
        }

        self.pipeline.run(
            protocol_dir='protocols/quiet',
            db=self.db,
            input_envelopes=[sync_envelope]
        )


@pytest.fixture
def test_context():
    """Provide a test context with single database and helper methods."""
    db = sqlite3.connect(':memory:')
    pipeline = PipelineRunner(verbose=False)
    context = ScenarioTestContext(db, pipeline)

    yield context

    # Cleanup
    db.close()