"""
Integration tests for all commands to verify database state after execution.

These tests verify that running commands produces the expected database state.
"""
import pytest
import json
import time
from pathlib import Path
import sys

# Add project root to path
protocol_dir = Path(__file__).parent.parent.parent
project_root = protocol_dir.parent.parent
sys.path.insert(0, str(project_root))

from core.db import get_connection, init_database
from core.pipeline import PipelineRunner
from core.commands import command_registry
from core.crypto import generate_keypair, sign


class TestCommandsToDatabase:
    """Integration tests for all commands verifying database state."""
    
    @pytest.fixture
    def db_conn(self, temp_db):
        """Create an initialized database connection."""
        conn = get_connection(temp_db)
        init_database(conn, str(protocol_dir))
        yield conn
        conn.close()
    
    @pytest.fixture
    def api_client(self, db_conn, temp_db):
        """Create a direct API client."""
        runner = PipelineRunner(db_path=temp_db, verbose=False)
        # Disable pipeline output during tests
        import logging
        logging.getLogger().setLevel(logging.ERROR)
        
        # Register commands from event directories
        from pathlib import Path
        events_dir = Path(protocol_dir) / "events"
        if events_dir.exists():
            for event_dir in events_dir.iterdir():
                if event_dir.is_dir() and (event_dir / "commands.py").exists():
                    try:
                        import importlib
                        module_path = f'protocols.quiet.events.{event_dir.name}.commands'
                        commands_module = importlib.import_module(module_path)
                        
                        for attr_name in dir(commands_module):
                            if attr_name.startswith('create_') or attr_name == 'join_network':
                                command_func = getattr(commands_module, attr_name)
                                if callable(command_func):
                                    command_registry.register(attr_name, command_func)
                    except ImportError as e:
                        pass
        
        class SimpleAPIClient:
            def __init__(self, runner, db):
                self.runner = runner
                self.db = db
                
            def execute_command(self, command_name, params):
                """Execute a command and process the pipeline."""
                try:
                    # Execute command
                    envelopes = command_registry.execute(command_name, params, self.db)
                    
                    # Process envelopes through pipeline
                    if envelopes:
                        self.runner.run(
                            protocol_dir=str(protocol_dir),
                            input_envelopes=envelopes
                        )
                    
                    # Return result
                    result = {}
                    if envelopes and len(envelopes) > 0:
                        # Extract key data from envelopes
                        for env in envelopes:
                            event = env.get('event_plaintext', {})
                            event_type = event.get('type')
                            
                            # Map common fields
                            if event_type == 'network':
                                result['network_id'] = event.get('network_id')
                            elif event_type == 'identity':
                                result['identity_id'] = event.get('peer_id')
                                result['peer_id'] = event.get('peer_id')
                            elif event_type == 'group':
                                result['group_id'] = event.get('group_id')
                            elif event_type == 'channel':
                                result['channel_id'] = event.get('channel_id')
                            elif event_type == 'message':
                                result['message_id'] = event.get('message_id')
                            elif event_type == 'key':
                                result['key_id'] = event.get('key_id')
                            elif event_type == 'invite':
                                result['invite_code'] = event.get('invite_code')
                            elif event_type == 'member':
                                result['added'] = True
                    
                    return {
                        "status": "ok",
                        "result": result
                    }
                except Exception as e:
                    return {
                        "status": "error",
                        "error": str(e)
                    }
        
        return SimpleAPIClient(runner, db_conn)
    
    @pytest.fixture
    def dump_database(self, db_conn):
        """Helper to dump entire database state."""
        def _dump():
            cursor = db_conn.cursor()
            result = {}
            
            # Get all tables
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """)
            tables = [row[0] for row in cursor.fetchall()]
            
            # Dump each table
            for table in tables:
                cursor.execute(f"SELECT * FROM {table}")
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                result[table] = {
                    "columns": columns,
                    "rows": [dict(zip(columns, row)) for row in rows]
                }
            
            return result
        return _dump
    
    @pytest.mark.integration
    def test_create_network_command(self, api_client, dump_database):
        """Test create_network command creates proper database state."""
        # Execute command
        response = api_client.execute_command("create_network", {
            "name": "Test Network",
            "description": "A test network for integration testing"
        })
        
        # Print error for debugging
        if response["status"] == "error":
            print(f"Error: {response['error']}")
        
        assert response["status"] == "ok"
        network_id = response["result"]["network_id"]
        
        # Verify database state
        db_state = dump_database()
        
        # Check events table
        events = db_state["events"]["rows"]
        assert len(events) == 2  # Network event + Identity event
        
        network_event = next(e for e in events if e["event_type"] == "network")
        assert network_event["network_id"] == network_id
        assert json.loads(network_event["event_data"])["name"] == "Test Network"
        
        identity_event = next(e for e in events if e["event_type"] == "identity")
        assert identity_event["network_id"] == network_id
        
        # Check projections
        networks = db_state["networks"]["rows"]
        assert len(networks) == 1
        assert networks[0]["network_id"] == network_id
        assert networks[0]["name"] == "Test Network"
        
        identities = db_state["identities"]["rows"]
        assert len(identities) == 1
        assert identities[0]["network_id"] == network_id
    
    @pytest.mark.integration
    def test_create_identity_command(self, api_client, dump_database):
        """Test create_identity command creates proper database state."""
        # First create a network
        network_response = api_client.execute_command("create_network", {
            "name": "Test Network"
        })
        network_id = network_response["result"]["network_id"]
        
        # Create another identity
        response = api_client.execute_command("create_identity", {
            "network_id": network_id
        })
        
        assert response["status"] == "ok"
        
        # Verify database state
        db_state = dump_database()
        
        # Should have 3 events (network, first identity, second identity)
        events = db_state["events"]["rows"]
        assert len(events) == 3
        
        identity_events = [e for e in events if e["event_type"] == "identity"]
        assert len(identity_events) == 2
        
        # Check projections
        identities = db_state["identities"]["rows"]
        assert len(identities) == 2
        assert all(i["network_id"] == network_id for i in identities)
    
    @pytest.mark.integration
    def test_create_group_command(self, api_client, dump_database):
        """Test create_group command creates proper database state."""
        # Setup: create network
        network_response = api_client.execute_command("create_network", {
            "name": "Test Network"
        })
        network_id = network_response["result"]["network_id"]
        identity_id = network_response["result"]["identity_id"]
        
        # Create group
        response = api_client.execute_command("create_group", {
            "name": "Test Group",
            "network_id": network_id,
            "identity_id": identity_id
        })
        
        assert response["status"] == "ok"
        group_id = response["result"]["group_id"]
        
        # Verify database state
        db_state = dump_database()
        
        # Check events
        events = db_state["events"]["rows"]
        group_events = [e for e in events if e["event_type"] == "group"]
        assert len(group_events) == 1
        assert group_events[0]["network_id"] == network_id

        # Check member events (creator is automatically added as member)
        member_events = [e for e in events if e["event_type"] == "member"]
        assert len(member_events) == 1
        
        # Check projections
        groups = db_state["groups"]["rows"]
        assert len(groups) == 1
        assert groups[0]["group_id"] == group_id
        assert groups[0]["name"] == "Test Group"
        assert groups[0]["network_id"] == network_id
        assert groups[0]["owner_id"] == identity_id
        
        # Check group members
        members = db_state["group_members"]["rows"]
        assert len(members) == 1
        assert members[0]["group_id"] == group_id
        assert members[0]["user_id"] == identity_id
    
    @pytest.mark.integration
    def test_create_channel_command(self, api_client, dump_database):
        """Test create_channel command creates proper database state."""
        # Setup: create network and group
        network_response = api_client.execute_command("create_network", {
            "name": "Test Network"
        })
        network_id = network_response["result"]["network_id"]
        identity_id = network_response["result"]["identity_id"]
        
        group_response = api_client.execute_command("create_group", {
            "name": "Test Group",
            "network_id": network_id,
            "identity_id": identity_id
        })
        group_id = group_response["result"]["group_id"]
        
        # Create channel
        response = api_client.execute_command("create_channel", {
            "name": "general",
            "description": "General discussion",
            "group_id": group_id,
            "identity_id": identity_id
        })
        
        assert response["status"] == "ok"
        channel_id = response["result"]["channel_id"]
        
        # Verify database state
        db_state = dump_database()
        
        # Check events
        events = db_state["events"]["rows"]
        channel_events = [e for e in events if e["event_type"] == "channel"]
        assert len(channel_events) == 1
        
        # Check projections
        channels = db_state["channels"]["rows"]
        assert len(channels) == 1
        assert channels[0]["channel_id"] == channel_id
        assert channels[0]["name"] == "general"
        assert channels[0]["description"] == "General discussion"
        assert channels[0]["group_id"] == group_id
    
    @pytest.mark.integration
    def test_create_message_command(self, api_client, dump_database):
        """Test create_message command creates proper database state."""
        # Setup: create network, group, and channel
        network_response = api_client.execute_command("create_network", {
            "name": "Test Network"
        })
        network_id = network_response["result"]["network_id"]
        identity_id = network_response["result"]["identity_id"]
        
        group_response = api_client.execute_command("create_group", {
            "name": "Test Group",
            "network_id": network_id,
            "identity_id": identity_id
        })
        group_id = group_response["result"]["group_id"]
        
        channel_response = api_client.execute_command("create_channel", {
            "name": "general",
            "group_id": group_id,
            "identity_id": identity_id
        })
        channel_id = channel_response["result"]["channel_id"]
        
        # Create message
        response = api_client.execute_command("create_message", {
            "content": "Hello, world!",
            "channel_id": channel_id,
            "identity_id": identity_id
        })
        
        assert response["status"] == "ok"
        message_id = response["result"]["message_id"]
        
        # Verify database state
        db_state = dump_database()
        
        # Check events
        events = db_state["events"]["rows"]
        message_events = [e for e in events if e["event_type"] == "message"]
        assert len(message_events) == 1
        
        # Check projections
        messages = db_state["messages"]["rows"]
        assert len(messages) == 1
        assert messages[0]["message_id"] == message_id
        assert messages[0]["content"] == "Hello, world!"
        assert messages[0]["channel_id"] == channel_id
        assert messages[0]["author_id"] == identity_id
    
    @pytest.mark.integration
    def test_create_key_command(self, api_client, dump_database):
        """Test create_key command creates proper database state."""
        # Setup: create network and group
        network_response = api_client.execute_command("create_network", {
            "name": "Test Network"
        })
        network_id = network_response["result"]["network_id"]
        identity_id = network_response["result"]["identity_id"]
        
        group_response = api_client.execute_command("create_group", {
            "name": "Test Group",
            "network_id": network_id,
            "identity_id": identity_id
        })
        group_id = group_response["result"]["group_id"]
        
        # Create key
        response = api_client.execute_command("create_key", {
            "group_id": group_id,
            "network_id": network_id,
            "identity_id": identity_id
        })
        
        assert response["status"] == "ok"
        key_id = response["result"]["key_id"]
        
        # Verify database state
        db_state = dump_database()
        
        # Check events
        events = db_state["events"]["rows"]
        key_events = [e for e in events if e["event_type"] == "key"]
        assert len(key_events) == 1
        assert key_events[0]["network_id"] == network_id
        
        # Check projections
        keys = db_state["keys"]["rows"]
        assert len(keys) == 1
        assert keys[0]["key_id"] == key_id
        assert keys[0]["group_id"] == group_id
        assert keys[0]["created_by"] == identity_id
        
        # Check local key storage
        local_keys = db_state["local_keys"]["rows"]
        assert len(local_keys) == 1
        assert local_keys[0]["key_id"] == key_id
    
    @pytest.mark.integration
    def test_create_transit_secret_command(self, api_client, dump_database):
        """Test create_transit_secret command creates proper database state."""
        # Setup: create network
        network_response = api_client.execute_command("create_network", {
            "name": "Test Network"
        })
        network_id = network_response["result"]["network_id"]
        identity_id = network_response["result"]["identity_id"]
        
        # Create transit secret
        response = api_client.execute_command("create_transit_secret", {
            "network_id": network_id,
            "identity_id": identity_id
        })
        
        assert response["status"] == "ok"
        
        # Verify database state
        db_state = dump_database()
        
        # Check events
        events = db_state["events"]["rows"]
        transit_events = [e for e in events if e["event_type"] == "transit_secret"]
        assert len(transit_events) == 1
        assert transit_events[0]["network_id"] == network_id
        
        # Check local transit keys storage
        transit_keys = db_state["transit_keys"]["rows"]
        assert len(transit_keys) == 1
        assert transit_keys[0]["network_id"] == network_id
        assert transit_keys[0]["peer_id"] == identity_id
    
    @pytest.mark.integration
    def test_create_invite_command(self, api_client, dump_database):
        """Test create_invite command creates proper database state."""
        # Setup: create network
        network_response = api_client.execute_command("create_network", {
            "name": "Test Network"
        })
        network_id = network_response["result"]["network_id"]
        identity_id = network_response["result"]["identity_id"]
        
        # Create invite
        response = api_client.execute_command("create_invite", {
            "network_id": network_id,
            "identity_id": identity_id
        })
        
        assert response["status"] == "ok"
        invite_code = response["result"]["invite_code"]
        
        # Verify database state
        db_state = dump_database()
        
        # Check invites table
        invites = db_state["invites"]["rows"]
        assert len(invites) == 1
        assert invites[0]["invite_code"] == invite_code
        assert invites[0]["network_id"] == network_id
        assert invites[0]["created_by"] == identity_id
        assert invites[0]["used"] == 0
        assert invites[0]["expires_at"] > time.time()
    
    @pytest.mark.integration
    def test_join_network_command(self, api_client, dump_database, db_conn):
        """Test join_network command creates proper database state."""
        # Setup: create network and invite
        network_response = api_client.execute_command("create_network", {
            "name": "Test Network"
        })
        network_id = network_response["result"]["network_id"]
        identity_id = network_response["result"]["identity_id"]
        
        invite_response = api_client.execute_command("create_invite", {
            "network_id": network_id,
            "identity_id": identity_id
        })
        invite_code = invite_response["result"]["invite_code"]
        
        # Use the same API client - the commands handle identity switching internally
        new_api_client = api_client
        
        # Join network
        response = new_api_client.execute_command("join_network", {
            "invite_code": invite_code,
            "name": "New User"
        })
        
        assert response["status"] == "ok"
        new_identity_id = response["result"]["identity_id"]
        
        # Verify database state
        db_state = dump_database()
        
        # Check events
        events = db_state["events"]["rows"]
        identity_events = [e for e in events if e["event_type"] == "identity"]
        assert len(identity_events) == 2  # Original + new user
        
        # Check projections
        identities = db_state["identities"]["rows"]
        assert len(identities) == 2
        new_identity = next(i for i in identities if i["peer_id"] == new_identity_id)
        assert new_identity["network_id"] == network_id
        assert new_identity["name"] == "New User"
        
        # Check invite was marked as used
        invites = db_state["invites"]["rows"]
        assert len(invites) == 1
        assert invites[0]["used"] == 1
        assert invites[0]["used_by"] == new_identity_id
    
    @pytest.mark.integration
    def test_create_member_command(self, api_client, dump_database, db_conn):
        """Test create_member command creates proper database state."""
        # Setup: create network with two users and a group
        network_response = api_client.execute_command("create_network", {
            "name": "Test Network"
        })
        network_id = network_response["result"]["network_id"]
        owner_id = network_response["result"]["identity_id"]
        
        # Create invite and have second user join
        invite_response = api_client.execute_command("create_invite", {
            "network_id": network_id,
            "identity_id": owner_id
        })
        invite_code = invite_response["result"]["invite_code"]
        
        # Use the same API client
        new_api_client = api_client
        
        join_response = new_api_client.execute_command("join_network", {
            "invite_code": invite_code,
            "name": "Second User"
        })
        second_user_id = join_response["result"]["identity_id"]
        
        # Create group as owner
        group_response = api_client.execute_command("create_group", {
            "name": "Test Group",
            "network_id": network_id,
            "identity_id": owner_id
        })
        group_id = group_response["result"]["group_id"]
        
        # Add second user to group
        response = api_client.execute_command("create_member", {
            "group_id": group_id,
            "user_id": second_user_id,
            "identity_id": owner_id,
            "network_id": network_id
        })
        
        assert response["status"] == "ok"
        
        # Verify database state
        db_state = dump_database()
        
        # Check events
        events = db_state["events"]["rows"]
        member_events = [e for e in events if e["event_type"] == "member"]
        assert len(member_events) == 1
        
        # Check projections
        members = db_state["group_members"]["rows"]
        assert len(members) == 2  # Owner + added user
        member_ids = {m["user_id"] for m in members}
        assert owner_id in member_ids
        assert second_user_id in member_ids
    
    @pytest.mark.integration
    def test_system_dump_database_command(self, api_client, dump_database):
        """Test system.dump_database command returns full database state."""
        # Setup: create some data
        network_response = api_client.execute_command("create_network", {
            "name": "Test Network"
        })
        network_id = network_response["result"]["network_id"]
        identity_id = network_response["result"]["identity_id"]
        
        group_response = api_client.execute_command("create_group", {
            "name": "Test Group",
            "network_id": network_id,
            "identity_id": identity_id
        })
        
        # Execute dump command
        response = api_client.execute_command("system.dump_database", {})
        
        assert response["status"] == "ok"
        dump_result = response["result"]
        
        # Verify dump contains expected tables
        expected_tables = [
            "events", "identities", "networks", "groups", 
            "group_members", "channels", "messages", "keys",
            "local_keys", "transit_keys", "invites"
        ]
        
        for table in expected_tables:
            assert table in dump_result
            assert "columns" in dump_result[table]
            assert "rows" in dump_result[table]
        
        # Verify data is present
        assert len(dump_result["events"]["rows"]) >= 3  # network, identity, group
        assert len(dump_result["networks"]["rows"]) == 1
        assert len(dump_result["identities"]["rows"]) == 1
        assert len(dump_result["groups"]["rows"]) == 1
    
    @pytest.mark.integration
    def test_message_with_reply(self, api_client, dump_database):
        """Test creating a message with reply_to field."""
        # Setup: create network, group, channel, and original message
        network_response = api_client.execute_command("create_network", {
            "name": "Test Network"
        })
        network_id = network_response["result"]["network_id"]
        identity_id = network_response["result"]["identity_id"]
        
        group_response = api_client.execute_command("create_group", {
            "name": "Test Group",
            "network_id": network_id,
            "identity_id": identity_id
        })
        group_id = group_response["result"]["group_id"]
        
        channel_response = api_client.execute_command("create_channel", {
            "name": "general",
            "group_id": group_id,
            "identity_id": identity_id
        })
        channel_id = channel_response["result"]["channel_id"]
        
        # Create original message
        original_response = api_client.execute_command("create_message", {
            "content": "Original message",
            "channel_id": channel_id,
            "identity_id": identity_id
        })
        original_id = original_response["result"]["message_id"]
        
        # Create reply
        reply_response = api_client.execute_command("create_message", {
            "content": "This is a reply",
            "channel_id": channel_id,
            "identity_id": identity_id,
            "reply_to": original_id
        })
        
        assert reply_response["status"] == "ok"
        reply_id = reply_response["result"]["message_id"]
        
        # Verify database state
        db_state = dump_database()
        
        messages = db_state["messages"]["rows"]
        assert len(messages) == 2
        
        reply_message = next(m for m in messages if m["message_id"] == reply_id)
        assert reply_message["reply_to"] == original_id
    
    @pytest.mark.integration
    def test_invite_with_custom_code(self, api_client, dump_database):
        """Test creating an invite with a custom invite code."""
        # Setup: create network
        network_response = api_client.execute_command("create_network", {
            "name": "Test Network"
        })
        network_id = network_response["result"]["network_id"]
        identity_id = network_response["result"]["identity_id"]
        
        # Create invite with custom code
        custom_code = "MY-CUSTOM-CODE-123"
        response = api_client.execute_command("create_invite", {
            "network_id": network_id,
            "identity_id": identity_id,
            "invite_code": custom_code
        })
        
        assert response["status"] == "ok"
        assert response["result"]["invite_code"] == custom_code
        
        # Verify database state
        db_state = dump_database()
        
        invites = db_state["invites"]["rows"]
        assert len(invites) == 1
        assert invites[0]["invite_code"] == custom_code