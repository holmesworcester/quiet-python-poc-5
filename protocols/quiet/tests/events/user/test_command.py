"""
Tests for user join flow via API.
"""
import pytest
import base64
import json
import tempfile
from pathlib import Path
from core.api import APIClient
from core.db import get_connection


class TestUserJoinFlow:
    """Test user.join_as_user flow using sequential emission (no placeholders)."""

    @pytest.mark.unit
    def test_join_as_user_basic(self):
        with tempfile.NamedTemporaryFile(suffix='.db') as tmp:
            api = APIClient(protocol_dir=Path('protocols/quiet'), reset_db=True, db_path=Path(tmp.name))

            # Create a test invite link
            invite_data = {'invite_secret': 'test_secret_123', 'network_id': 'test_network', 'group_id': 'test_group'}
            invite_json = json.dumps(invite_data)
            invite_b64 = base64.b64encode(invite_json.encode()).decode()
            invite_link = f"quiet://invite/{invite_b64}"

            result = api.execute_operation('user.join_as_user', {'invite_link': invite_link, 'name': 'Alice'})
            assert 'identity' in result['ids'] and 'peer' in result['ids'] and 'user' in result['ids']

    @pytest.mark.unit
    def test_join_as_user_invalid_invite_link(self):
        with tempfile.NamedTemporaryFile(suffix='.db') as tmp:
            api = APIClient(protocol_dir=Path('protocols/quiet'), reset_db=True, db_path=Path(tmp.name))
            with pytest.raises(ValueError, match="Invalid invite link format"):
                api.execute_operation('user.join_as_user', {'invite_link': 'invalid://invite/abc', 'name': 'Alice'})
            with pytest.raises(ValueError, match="Invalid invite link encoding"):
                api.execute_operation('user.join_as_user', {'invite_link': 'quiet://invite/not_base64!!!', 'name': 'Alice'})
            invalid_invite_data = {'network_id': 'test'}
            invite_json = json.dumps(invalid_invite_data)
            invite_b64 = base64.b64encode(invite_json.encode()).decode()
            invite_link = f"quiet://invite/{invite_b64}"
            with pytest.raises(ValueError, match="Invalid invite data"):
                api.execute_operation('user.join_as_user', {'invite_link': invite_link, 'name': 'Alice'})

    @pytest.mark.unit
    def test_join_as_user_stores_identity(self):
        with tempfile.NamedTemporaryFile(suffix='.db') as tmp:
            api = APIClient(protocol_dir=Path('protocols/quiet'), reset_db=True, db_path=Path(tmp.name))
            invite_data = {'invite_secret': 'test_secret', 'network_id': 'test_network', 'group_id': 'test_group'}
            invite_json = json.dumps(invite_data)
            invite_b64 = base64.b64encode(invite_json.encode()).decode()
            invite_link = f"quiet://invite/{invite_b64}"
            api.execute_operation('user.join_as_user', {'invite_link': invite_link, 'name': 'Charlie'})

            # Check identity in protocol identities table
            db = get_connection(tmp.name)
            row = db.execute(
                "SELECT * FROM identities WHERE name = ? ORDER BY created_at DESC LIMIT 1",
                ("Charlie",)
            ).fetchone()
            assert row is not None
            assert row['name'] == 'Charlie'
            assert row['private_key'] is not None
            db.close()
