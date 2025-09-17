"""
Integration tests for join_as_user flow without placeholder logic.
"""
import base64
import json
import tempfile
from pathlib import Path
from core.api import APIClient
from core.db import get_connection


def test_join_as_user_basic():
    """Test basic join_as_user flow execution via API."""
    with tempfile.NamedTemporaryFile(suffix='.db') as tmp:
        api = APIClient(protocol_dir=Path('protocols/quiet'), reset_db=True, db_path=Path(tmp.name))

        invite_data = {'invite_secret': 'test_secret_123', 'network_id': 'test_network', 'group_id': 'test_group'}
        invite_json = json.dumps(invite_data)
        invite_b64 = base64.b64encode(invite_json.encode()).decode()
        invite_link = f'quiet://invite/{invite_b64}'

        result = api.execute_operation('user.join_as_user', {'invite_link': invite_link, 'name': 'Alice'})
        assert 'identity' in result['ids']
        assert 'peer' in result['ids']
        assert 'user' in result['ids']


def test_join_as_user_with_db_check():
    """Test join_as_user and verify database state via API and DB."""
    with tempfile.NamedTemporaryFile(suffix='.db') as tmp:
        api = APIClient(protocol_dir=Path('protocols/quiet'), reset_db=True, db_path=Path(tmp.name))

        invite_data = {'invite_secret': 'test_secret_123', 'network_id': 'test_network', 'group_id': 'test_group'}
        invite_json = json.dumps(invite_data)
        invite_b64 = base64.b64encode(invite_json.encode()).decode()
        invite_link = f'quiet://invite/{invite_b64}'

        result = api.execute_operation('user.join_as_user', {'invite_link': invite_link, 'name': 'Alice'})
        assert result['ids']['identity']

        # Check protocol identities table
        db = get_connection(tmp.name)
        row = db.execute("SELECT * FROM identities WHERE identity_id = ?", (result['ids']['identity'],)).fetchone()
        assert row is not None
        db.close()

