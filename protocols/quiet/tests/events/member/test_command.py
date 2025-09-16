"""
Tests for member commands.
"""
import pytest
import tempfile
import os
from protocols.quiet.events.member.commands import create_member
from core.db import get_connection, init_database


class TestMemberCommands:
    """Test member commands."""

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
        self.identity_id = 'test_identity_id'
        self.user_id = 'test_user_id'
        self.group_id = 'test_group_id'
        self.network_id = 'test_network_id'

    def teardown_method(self):
        """Clean up test database."""
        self.db.close()
        os.unlink(self.db_path)

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_member_envelope_structure(self):
        """Test that create_member generates correct envelope structure."""
        params = {
            'group_id': self.group_id,
            'user_id': self.user_id,
            'identity_id': self.identity_id,
            'network_id': self.network_id
        }

        envelope = create_member(params)

        # Check envelope structure
        assert envelope['event_type'] == 'member'
        assert envelope['self_created'] == True
        assert envelope['identity_id'] == self.identity_id
        assert envelope['network_id'] == self.network_id

        # Check dependencies
        assert set(envelope['deps']) == {f"group:{self.group_id}", f"user:{self.user_id}"}

        # Check event structure
        event = envelope['event_plaintext']
        assert event['type'] == 'member'
        assert event['group_id'] == self.group_id
        assert event['user_id'] == self.user_id
        assert event['added_by'] == self.identity_id
        assert event['network_id'] == self.network_id
        assert 'created_at' in event
        assert event['signature'] == ''  # Not signed yet

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_member_missing_group_id(self):
        """Test that create_member requires group_id."""
        params = {
            'user_id': self.user_id,
            'identity_id': self.identity_id,
            'network_id': self.network_id
            # Missing group_id
        }

        with pytest.raises(ValueError, match="group_id is required"):
            create_member(params)

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_member_missing_user_id(self):
        """Test that create_member requires user_id."""
        params = {
            'group_id': self.group_id,
            'identity_id': self.identity_id,
            'network_id': self.network_id
            # Missing user_id
        }

        with pytest.raises(ValueError, match="user_id is required"):
            create_member(params)

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_member_missing_identity_id(self):
        """Test that create_member requires identity_id."""
        params = {
            'group_id': self.group_id,
            'user_id': self.user_id,
            'network_id': self.network_id
            # Missing identity_id
        }

        with pytest.raises(ValueError, match="identity_id is required"):
            create_member(params)

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_member_missing_network_id(self):
        """Test that create_member requires network_id."""
        params = {
            'group_id': self.group_id,
            'user_id': self.user_id,
            'identity_id': self.identity_id
            # Missing network_id
        }

        with pytest.raises(ValueError, match="network_id is required"):
            create_member(params)

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_member_empty_group_id(self):
        """Test that create_member requires non-empty group_id."""
        params = {
            'group_id': '',  # Empty group_id
            'user_id': self.user_id,
            'identity_id': self.identity_id,
            'network_id': self.network_id
        }

        with pytest.raises(ValueError, match="group_id is required"):
            create_member(params)

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_member_empty_user_id(self):
        """Test that create_member requires non-empty user_id."""
        params = {
            'group_id': self.group_id,
            'user_id': '',  # Empty user_id
            'identity_id': self.identity_id,
            'network_id': self.network_id
        }

        with pytest.raises(ValueError, match="user_id is required"):
            create_member(params)

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_member_dependency(self):
        """Test that create_member depends on group and user."""
        params = {
            'group_id': 'group_123',
            'user_id': 'user_456',
            'identity_id': self.identity_id,
            'network_id': self.network_id
        }

        envelope = create_member(params)

        # Should depend on both group and user
        assert len(envelope['deps']) == 2
        assert 'group:group_123' in envelope['deps']
        assert 'user:user_456' in envelope['deps']

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_member_timestamp(self):
        """Test that create_member includes timestamp."""
        params = {
            'group_id': self.group_id,
            'user_id': self.user_id,
            'identity_id': self.identity_id,
            'network_id': self.network_id
        }

        envelope = create_member(params)

        event = envelope['event_plaintext']
        assert 'created_at' in event
        assert isinstance(event['created_at'], int)
        assert event['created_at'] > 0

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_multiple_members(self):
        """Test creating multiple members for same group."""
        # Create first member
        envelope1 = create_member({
            'group_id': self.group_id,
            'user_id': 'user_1',
            'identity_id': self.identity_id,
            'network_id': self.network_id
        })

        # Create second member
        envelope2 = create_member({
            'group_id': self.group_id,
            'user_id': 'user_2',
            'identity_id': self.identity_id,
            'network_id': self.network_id
        })

        # Should have different user_ids
        assert envelope1['event_plaintext']['user_id'] == 'user_1'
        assert envelope2['event_plaintext']['user_id'] == 'user_2'

        # But same group_id and added_by
        assert envelope1['event_plaintext']['group_id'] == envelope2['event_plaintext']['group_id']
        assert envelope1['event_plaintext']['added_by'] == envelope2['event_plaintext']['added_by']

    @pytest.mark.unit
    @pytest.mark.event_type
    def test_create_member_added_by(self):
        """Test that added_by matches identity_id."""
        params = {
            'group_id': self.group_id,
            'user_id': self.user_id,
            'identity_id': 'admin_identity',
            'network_id': self.network_id
        }

        envelope = create_member(params)

        event = envelope['event_plaintext']
        assert event['added_by'] == 'admin_identity'
        assert envelope['identity_id'] == 'admin_identity'