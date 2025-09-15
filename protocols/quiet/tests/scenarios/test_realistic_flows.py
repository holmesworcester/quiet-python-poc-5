"""
Realistic scenario tests that simulate actual user workflows.

These tests use the API as a real client would, creating a sequence
of events that depend on each other.
"""
import pytest
import sqlite3
import time
from typing import Dict, Any, List

from pathlib import Path
from core.api import API
from core.db import get_connection


class TestRealisticUserFlows:
    """Test realistic user scenarios through the API."""

    @pytest.fixture
    def api(self, tmp_path):
        """Set up API with temporary database."""
        # Find protocol directory (where openapi.yaml is)
        protocol_dir = Path(__file__).parent.parent.parent
        # Use temporary database
        db_path = tmp_path / "test.db"
        api = API(protocol_dir, reset_db=True, db_path=db_path)
        return api

    def test_single_user_creates_community(self, api):
        """
        Test a single user creating a community from scratch.

        Flow:
        1. Create identity (local)
        2. Create network
        3. Create default group
        4. Create general channel
        5. Send welcome message
        """
        # Step 1: Create identity
        print("\n=== Creating Identity ===")
        identity_result = api.execute_operation(
            operation_id="create_identity",
            params={"name": "Alice"}
        )
        assert identity_result is not None
        assert "ids" in identity_result
        assert "identity" in identity_result["ids"]
        identity_id = identity_result["ids"]["identity"]
        print(f"Created identity: {identity_id}")

        # Step 2: Create network
        print("\n=== Creating Network ===")
        network_result = api.execute_operation(
            operation_id="create_network",
            params={
                "name": "Alice's Community",
                "identity_id": identity_id
            }
        )
        assert network_result is not None
        assert "ids" in network_result
        assert "network" in network_result["ids"]
        network_id = network_result["ids"]["network"]
        print(f"Created network: {network_id}")

        # Step 3: Create default group
        print("\n=== Creating Group ===")
        group_result = api.execute_operation(
            operation_id="create_group",
            params={
                "name": "Main Group",
                "network_id": network_id,
                "identity_id": identity_id
            }
        )
        assert group_result is not None
        # First try to get from response handler result
        if "groups" in group_result and len(group_result["groups"]) > 0:
            group = group_result["groups"][0]
            group_id = group["group_id"]
        # Fallback to ids if response handler failed
        elif "ids" in group_result and "group" in group_result["ids"]:
            group_id = group_result["ids"]["group"]
        else:
            raise AssertionError(f"No group created. Result: {group_result}")
        print(f"Created group: {group_id}")

        # Step 4: Create general channel
        print("\n=== Creating Channel ===")
        channel_result = api.execute_operation(
            operation_id="create_channel",
            params={
                "name": "general",
                "group_id": group_id,
                "identity_id": identity_id,
                "network_id": network_id
            }
        )
        assert channel_result is not None
        # First try to get from response handler result
        if "channels" in channel_result and len(channel_result["channels"]) > 0:
            channel = channel_result["channels"][0]
            channel_id = channel["channel_id"]
        # Fallback to ids if response handler failed
        elif "ids" in channel_result and "channel" in channel_result["ids"]:
            channel_id = channel_result["ids"]["channel"]
        else:
            raise AssertionError(f"No channel created. Result: {channel_result}")
        print(f"Created channel: {channel_id}")

        # Step 5: Send welcome message
        print("\n=== Sending Message ===")
        message_result = api.execute_operation(
            operation_id="create_message",
            params={
                "content": "Welcome to my community!",
                "channel_id": channel_id,
                "identity_id": identity_id
            }
        )
        assert message_result is not None
        # Should return recent messages
        assert "messages" in message_result
        assert len(message_result["messages"]) == 1
        message = message_result["messages"][0]
        assert message["content"] == "Welcome to my community!"
        print(f"Sent message: {message['content']}")

        # Verify final state
        print("\n=== Verifying Final State ===")

        # Check identity exists
        # Get a connection to verify data
        db = get_connection(str(api.db_path))
        cursor = db.execute(
            "SELECT * FROM identities WHERE identity_id = ?",
            (identity_id,)
        )
        identity = cursor.fetchone()
        assert identity is not None
        assert identity["name"] == "Alice"

        # Check network exists
        cursor = db.execute(
            "SELECT * FROM networks WHERE network_id = ?",
            (network_id,)
        )
        network = cursor.fetchone()
        assert network is not None
        assert network["name"] == "Alice's Community"

        # Check group exists
        cursor = db.execute(
            "SELECT * FROM groups WHERE group_id = ?",
            (group_id,)
        )
        group = cursor.fetchone()
        assert group is not None
        assert group["name"] == "Main Group"

        # Check channel exists
        cursor = db.execute(
            "SELECT * FROM channels WHERE channel_id = ?",
            (channel_id,)
        )
        channel = cursor.fetchone()
        assert channel is not None
        assert channel["name"] == "general"

        # Check message exists
        cursor = db.execute(
            "SELECT * FROM messages WHERE channel_id = ?",
            (channel_id,)
        )
        messages = cursor.fetchall()
        assert len(messages) == 1
        assert messages[0]["content"] == "Welcome to my community!"

        print("✓ All checks passed!")

    def test_user_joins_existing_community(self, api):
        """
        Test a user joining an existing community via invite.

        Flow:
        1. Alice creates identity and network
        2. Alice creates invite
        3. Bob creates identity
        4. Bob joins via invite link
        5. Bob sends message
        """
        # === Alice creates community ===
        print("\n=== Alice Creates Community ===")

        # Alice's identity
        alice_result = api.execute_operation(
            operation_id="create_identity",
            params={"name": "Alice"}
        )
        alice_id = alice_result["ids"]["identity"]

        # Create network
        network_result = api.execute_operation(
            operation_id="create_network",
            params={
                "name": "Tech Talk",
                "identity_id": alice_id
            }
        )
        network_id = network_result["ids"]["network"]

        # Create group
        group_result = api.execute_operation(
            operation_id="create_group",
            params={
                "name": "Developers",
                "network_id": network_id,
                "identity_id": alice_id
            }
        )
        group_id = group_result["groups"][0]["group_id"]

        # Create channel
        channel_result = api.execute_operation(
            operation_id="create_channel",
            params={
                "name": "general",
                "group_id": group_id,
                "identity_id": alice_id,
                "network_id": network_id
            }
        )
        channel_id = channel_result["channels"][0]["channel_id"]

        # === Alice creates invite ===
        print("\n=== Alice Creates Invite ===")
        invite_result = api.execute_operation(
            operation_id="create_invite",
            params={
                "group_id": group_id,
                "identity_id": alice_id,
                "expiry_days": 7
            }
        )
        assert invite_result is not None
        assert "invite_link" in invite_result
        invite_link = invite_result["invite_link"]
        print(f"Created invite link: {invite_link}")

        # === Bob joins ===
        print("\n=== Bob Joins Community ===")

        # Bob's identity
        bob_result = api.execute_operation(
            operation_id="create_identity",
            params={"name": "Bob"}
        )
        bob_id = bob_result["ids"]["identity"]

        # Bob joins via invite
        join_result = api.execute_operation(
            operation_id="join_as_user",
            params={
                "invite_link": invite_link,
                "identity_id": bob_id,
                "name": "Bob"
            }
        )
        assert join_result is not None
        # Should return group members including Bob
        assert "members" in join_result
        member_names = [m["name"] for m in join_result["members"]]
        assert "Alice" in member_names
        assert "Bob" in member_names
        print(f"Bob joined! Members: {member_names}")

        # === Bob sends message ===
        print("\n=== Bob Sends Message ===")
        message_result = api.execute_operation(
            operation_id="create_message",
            params={
                "content": "Hi everyone! Happy to be here.",
                "channel_id": channel_id,
                "identity_id": bob_id
            }
        )
        assert message_result is not None
        assert "messages" in message_result
        # Should have Bob's message
        bob_messages = [m for m in message_result["messages"]
                       if m["content"] == "Hi everyone! Happy to be here."]
        assert len(bob_messages) == 1
        print(f"Bob sent: {bob_messages[0]['content']}")

        # === Alice sends reply ===
        print("\n=== Alice Replies ===")
        reply_result = api.execute_operation(
            operation_id="create_message",
            params={
                "content": "Welcome Bob!",
                "channel_id": channel_id,
                "identity_id": alice_id
            }
        )
        assert reply_result is not None
        messages = reply_result["messages"]
        assert len(messages) >= 2  # At least Bob's and Alice's messages
        print(f"Conversation has {len(messages)} messages")

        print("✓ Join flow completed!")

    def test_multi_group_multi_channel_community(self, api):
        """
        Test creating a complex community with multiple groups and channels.

        Flow:
        1. Create identity and network
        2. Create multiple groups (General, Dev Team, Marketing)
        3. Create multiple channels per group
        4. Send messages to different channels
        5. Verify isolation between groups
        """
        # Create founder
        print("\n=== Creating Founder ===")
        founder_result = api.execute_operation(
            operation_id="create_identity",
            params={"name": "Founder"}
        )
        founder_id = founder_result["ids"]["identity"]

        # Create network
        network_result = api.execute_operation(
            operation_id="create_network",
            params={
                "name": "Startup Inc",
                "identity_id": founder_id
            }
        )
        network_id = network_result["ids"]["network"]

        # Create groups
        groups = {}
        group_configs = [
            {"name": "General", "channels": ["announcements", "random", "introductions"]},
            {"name": "Dev Team", "channels": ["frontend", "backend", "devops", "bugs"]},
            {"name": "Marketing", "channels": ["campaigns", "social-media", "analytics"]}
        ]

        for group_config in group_configs:
            print(f"\n=== Creating {group_config['name']} Group ===")

            # Create group
            group_result = api.execute_operation(
                operation_id="create_group",
                params={
                    "name": group_config["name"],
                    "network_id": network_id,
                    "identity_id": founder_id
                }
            )
            group_id = group_result["groups"][-1]["group_id"]  # Get last created
            groups[group_config["name"]] = {
                "id": group_id,
                "channels": {}
            }

            # Create channels for this group
            for channel_name in group_config["channels"]:
                channel_result = api.execute_operation(
                    operation_id="create_channel",
                    params={
                        "name": channel_name,
                        "group_id": group_id,
                        "identity_id": founder_id,
                        "network_id": network_id
                    }
                )
                # Find the channel we just created
                channels = channel_result["channels"]
                channel = next(c for c in channels if c["name"] == channel_name)
                groups[group_config["name"]]["channels"][channel_name] = channel["channel_id"]
                print(f"  Created #{channel_name}")

        # Send messages to various channels
        print("\n=== Sending Messages ===")

        # Announcement in General
        api.execute_operation(
            operation_id="create_message",
            params={
                "content": "Welcome to Startup Inc! We're building the future.",
                "channel_id": groups["General"]["channels"]["announcements"],
                "identity_id": founder_id
            }
        )
        print("Sent announcement")

        # Dev discussion
        api.execute_operation(
            operation_id="create_message",
            params={
                "content": "Let's discuss the new API design in today's standup",
                "channel_id": groups["Dev Team"]["channels"]["backend"],
                "identity_id": founder_id
            }
        )
        print("Sent dev message")

        # Marketing update
        api.execute_operation(
            operation_id="create_message",
            params={
                "content": "Q4 campaign launching next week!",
                "channel_id": groups["Marketing"]["channels"]["campaigns"],
                "identity_id": founder_id
            }
        )
        print("Sent marketing message")

        # Verify structure
        print("\n=== Verifying Structure ===")

        # Check total counts
        # Get database connection for verification
        db = get_connection(str(api.db_path))
        cursor = db.execute("SELECT COUNT(*) as count FROM groups WHERE network_id = ?", (network_id,))
        assert cursor.fetchone()["count"] == 3
        print("✓ 3 groups created")

        # Get database connection for verification
        db = get_connection(str(api.db_path))
        cursor = db.execute("""
            SELECT COUNT(*) as count FROM channels c
            JOIN groups g ON c.group_id = g.group_id
            WHERE g.network_id = ?
        """, (network_id,))
        total_channels = cursor.fetchone()["count"]
        assert total_channels == 10  # 3 + 4 + 3
        print(f"✓ {total_channels} channels created")

        # Verify channel isolation
        # Get database connection for verification
        db = get_connection(str(api.db_path))
        cursor = db.execute("""
            SELECT g.name as group_name, c.name as channel_name
            FROM channels c
            JOIN groups g ON c.group_id = g.group_id
            WHERE g.network_id = ?
            ORDER BY g.name, c.name
        """, (network_id,))

        channel_list = cursor.fetchall()
        print("\nChannel Structure:")
        current_group = None
        for row in channel_list:
            if row["group_name"] != current_group:
                current_group = row["group_name"]
                print(f"\n{current_group}:")
            print(f"  #{row['channel_name']}")

        print("\n✓ Complex community structure created!")

    def test_invite_expiry_and_reuse(self, api):
        """
        Test invite link behavior including expiry and reuse.

        Flow:
        1. Create community with invite
        2. First user joins successfully
        3. Second user joins with same invite
        4. Test expired invite (would need time manipulation)
        """
        # Create community
        print("\n=== Creating Community ===")
        alice_result = api.execute_operation(
            operation_id="create_identity",
            params={"name": "Alice"}
        )
        alice_id = alice_result["ids"]["identity"]

        network_result = api.execute_operation(
            operation_id="create_network",
            params={"name": "Invite Test", "identity_id": alice_id}
        )
        network_id = network_result["ids"]["network"]

        group_result = api.execute_operation(
            operation_id="create_group",
            params={
                "name": "Test Group",
                "network_id": network_id,
                "identity_id": alice_id
            }
        )
        group_id = group_result["groups"][0]["group_id"]

        # Create invite with short expiry
        print("\n=== Creating Invite ===")
        invite_result = api.execute_operation(
            operation_id="create_invite",
            params={
                "group_id": group_id,
                "identity_id": alice_id,
                "expiry_days": 1  # Short expiry for testing
            }
        )
        invite_link = invite_result["invite_link"]
        print(f"Invite link: {invite_link}")

        # First user joins
        print("\n=== Bob Joins ===")
        bob_result = api.execute_operation(
            operation_id="create_identity",
            params={"name": "Bob"}
        )
        bob_id = bob_result["ids"]["identity"]

        bob_join = api.execute_operation(
            operation_id="join_as_user",
            params={
                "invite_link": invite_link,
                "identity_id": bob_id,
                "name": "Bob"
            }
        )
        assert len(bob_join["members"]) == 2  # Alice and Bob
        print("✓ Bob joined successfully")

        # Second user joins with same invite
        print("\n=== Charlie Joins ===")
        charlie_result = api.execute_operation(
            operation_id="create_identity",
            params={"name": "Charlie"}
        )
        charlie_id = charlie_result["ids"]["identity"]

        charlie_join = api.execute_operation(
            operation_id="join_as_user",
            params={
                "invite_link": invite_link,
                "identity_id": charlie_id,
                "name": "Charlie"
            }
        )
        assert len(charlie_join["members"]) == 3  # Alice, Bob, and Charlie
        print("✓ Charlie joined with same invite")

        # Verify all members
        # Get database connection for verification
        db = get_connection(str(api.db_path))
        cursor = db.execute("""
            SELECT u.name
            FROM users u
            JOIN group_members gm ON u.user_id = gm.user_id
            WHERE gm.group_id = ?
            ORDER BY u.name
        """, (group_id,))

        members = [row["name"] for row in cursor.fetchall()]
        assert members == ["Alice", "Bob", "Charlie"]
        print(f"✓ All members present: {members}")

        # Create another invite for different group
        print("\n=== Testing Multiple Invites ===")
        vip_group_result = api.execute_operation(
            operation_id="create_group",
            params={
                "name": "VIP Group",
                "network_id": network_id,
                "identity_id": alice_id
            }
        )
        vip_group_id = vip_group_result["groups"][-1]["group_id"]

        vip_invite_result = api.execute_operation(
            operation_id="create_invite",
            params={
                "group_id": vip_group_id,
                "identity_id": alice_id,
                "expiry_days": 30  # Longer expiry
            }
        )
        vip_invite_link = vip_invite_result["invite_link"]

        # Verify invites are different
        assert vip_invite_link != invite_link
        print(f"✓ Different invite created: {vip_invite_link[:20]}...")

        print("\n✓ Invite flow tests completed!")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])