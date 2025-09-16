"""
Tests for message commands.
"""
import pytest
import tempfile
import os
from protocols.quiet.events.message.commands import create_message
from core.db import get_connection, init_database


class TestMessageCommands:
    """Test message commands."""

    def setup_method(self):
        """Set up test database."""
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        os.close(self.db_fd)
        self.db = get_connection(self.db_path)

        # Get the protocol directory properly
        import pathlib
        test_dir = pathlib.Path(__file__).parent
        protocol_dir = test_dir.parent.parent.parent
        init_database(self.db, str(protocol_dir))

        # Set up test data
        self.peer_id = 'test_peer_id'
        self.channel_id = 'test_channel_id'

    def teardown_method(self):
        """Clean up test database."""
        self.db.close()
        os.unlink(self.db_path)

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_message_envelope_structure(self):
        """Test that create_message generates correct envelope structure."""
        params = {
            'content': 'Hello, world!',
            'channel_id': self.channel_id,
            'peer_id': self.peer_id
        }

        envelope = create_message(params)

        # Check envelope structure
        assert envelope['event_type'] == 'message'
        assert envelope['self_created'] == True
        assert envelope['peer_id'] == self.peer_id
        assert envelope['network_id'] == ''  # Will be filled by resolve_deps

        # Check dependencies
        assert f"channel:{self.channel_id}" in envelope['deps']
        assert f"peer:{self.peer_id}" in envelope['deps']

        # Check event structure
        event = envelope['event_plaintext']
        assert event['type'] == 'message'
        assert event['message_id'] == ''  # Will be filled by encrypt handler
        assert event['channel_id'] == self.channel_id
        assert event['group_id'] == ''  # Will be filled by resolve_deps
        assert event['network_id'] == ''  # Will be filled by resolve_deps
        assert event['peer_id'] == self.peer_id
        assert event['content'] == 'Hello, world!'
        assert 'created_at' in event
        assert event['signature'] == ''  # Not signed yet

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_message_dependencies(self):
        """Test that create_message sets correct dependencies."""
        params = {
            'content': 'Test message',
            'channel_id': 'channel_123',
            'peer_id': 'peer_456'
        }

        envelope = create_message(params)

        # Should depend on channel and peer
        assert len(envelope['deps']) == 2
        assert "channel:channel_123" in envelope['deps']
        assert "peer:peer_456" in envelope['deps']

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_message_empty_content(self):
        """Test that create_message handles empty content."""
        params = {
            'content': '',  # Empty content
            'channel_id': self.channel_id,
            'peer_id': self.peer_id
        }

        envelope = create_message(params)

        # Should use default message
        event = envelope['event_plaintext']
        assert event['content'] == 'empty message'

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_message_missing_content(self):
        """Test that create_message handles missing content."""
        params = {
            # No content field
            'channel_id': self.channel_id,
            'peer_id': self.peer_id
        }

        envelope = create_message(params)

        # Should use default message
        event = envelope['event_plaintext']
        assert event['content'] == 'empty message'

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_message_missing_peer_id(self):
        """Test that create_message requires peer_id."""
        params = {
            'content': 'Test message',
            'channel_id': self.channel_id
            # Missing peer_id
        }

        with pytest.raises(ValueError, match="peer_id is required"):
            create_message(params)

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_message_default_channel(self):
        """Test that create_message uses default channel if not provided."""
        params = {
            'content': 'Test message',
            # No channel_id
            'peer_id': self.peer_id
        }

        envelope = create_message(params)

        # Should use dummy channel
        event = envelope['event_plaintext']
        assert event['channel_id'] == 'dummy-channel-id'

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_message_timestamp(self):
        """Test that create_message includes timestamp."""
        params = {
            'content': 'Test message',
            'channel_id': self.channel_id,
            'peer_id': self.peer_id
        }

        envelope = create_message(params)

        event = envelope['event_plaintext']
        assert 'created_at' in event
        assert isinstance(event['created_at'], int)
        assert event['created_at'] > 0