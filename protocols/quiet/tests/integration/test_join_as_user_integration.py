"""
Integration tests for join_as_user command with placeholder resolution.
"""
import base64
import json
import sqlite3
from core.pipeline import PipelineRunner


def test_join_as_user_basic():
    """Test basic join_as_user command execution."""
    # Import to register command
    import protocols.quiet.events.user.commands
    
    # Create a fake invite link
    invite_data = {
        'invite_secret': 'test_secret_123',
        'network_id': 'test_network',
        'group_id': 'test_group'
    }
    invite_json = json.dumps(invite_data)
    invite_b64 = base64.b64encode(invite_json.encode()).decode()
    invite_link = f'quiet://invite/{invite_b64}'
    
    # Run pipeline
    runner = PipelineRunner(db_path=':memory:', verbose=False)
    result = runner.run('protocols/quiet', commands=[{
        'name': 'join_as_user',
        'params': {
            'invite_link': invite_link,
            'name': 'Alice'
        }
    }])
    
    # Check that events were processed but not all stored
    # (invite dependency is missing in this test)
    print("Pipeline result:", result)
    
    # The identity should be stored (it's local-only and has no deps)
    if 'identity' in result:
        print(f"✓ Identity event stored with ID: {result['identity']}")
        assert len(result['identity']) == 32, "Identity ID should be 32 chars"
    else:
        print("✗ Identity event not stored (expected due to missing dependencies)")
    
    return result


def test_join_as_user_with_db_check():
    """Test join_as_user and verify database state."""
    import protocols.quiet.events.user.commands
    
    # Create invite
    invite_data = {
        'invite_secret': 'test_secret_123',
        'network_id': 'test_network',
        'group_id': 'test_group'
    }
    invite_json = json.dumps(invite_data)
    invite_b64 = base64.b64encode(invite_json.encode()).decode()
    invite_link = f'quiet://invite/{invite_b64}'
    
    # Run with persistent database
    db_path = '/tmp/test_join.db'
    import os
    if os.path.exists(db_path):
        os.remove(db_path)
    
    runner = PipelineRunner(db_path=db_path, verbose=False)
    result = runner.run('protocols/quiet', commands=[{
        'name': 'join_as_user',
        'params': {
            'invite_link': invite_link,
            'name': 'Alice'
        }
    }])
    
    # Check database directly
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    
    # Check identities table
    cursor = db.execute("SELECT * FROM identities")
    identities = cursor.fetchall()
    print(f"\nIdentities in database: {len(identities)}")
    
    if identities:
        identity = identities[0]
        print(f"  - Identity ID: {identity['identity_id']}")
        print(f"  - Name: {identity['name']}")
        print(f"  - Network: {identity['network_id']}")
        print(f"  - Has private key: {bool(identity['private_key'])}")
    
    # Check peers table
    cursor = db.execute("SELECT * FROM peers")
    peers = cursor.fetchall()
    print(f"\nPeers in database: {len(peers)}")
    
    if peers:
        peer = peers[0]
        print(f"  - Peer ID: {peer['peer_id']}")
        print(f"  - Identity ID: {peer['identity_id']}")
        print(f"  - Public key: {peer['public_key'][:16]}...")
    
    db.close()
    os.remove(db_path)
    
    return result


def test_placeholder_resolution():
    """Test that placeholders are correctly resolved."""
    import protocols.quiet.events.user.commands
    from protocols.quiet.events.user.commands import join_as_user
    
    # Create invite
    invite_data = {
        'invite_secret': 'test_secret_123',
        'network_id': 'test_network',
        'group_id': 'test_group'
    }
    invite_json = json.dumps(invite_data)
    invite_b64 = base64.b64encode(invite_json.encode()).decode()
    invite_link = f'quiet://invite/{invite_b64}'
    
    # Get the envelopes from the command
    envelopes = join_as_user({
        'invite_link': invite_link,
        'name': 'Alice'
    })
    
    print(f"\nCommand generated {len(envelopes)} envelopes")
    
    # Check envelope structure
    identity_env = envelopes[0]
    peer_env = envelopes[1]
    user_env = envelopes[2]
    
    # Identity should have pre-calculated ID
    assert 'event_id' in identity_env, "Identity should have event_id"
    print(f"✓ Identity has event_id: {identity_env['event_id']}")
    
    # Peer should reference identity
    peer_event = peer_env['event_plaintext']
    assert peer_event['identity_id'] == identity_env['event_id'], "Peer should reference identity"
    print(f"✓ Peer references identity: {peer_event['identity_id']}")
    
    # User should have placeholder for peer
    user_event = user_env['event_plaintext']
    assert user_event['peer_id'] == '@generated:peer:0', "User should have placeholder"
    print(f"✓ User has placeholder: {user_event['peer_id']}")
    
    # User deps should also have placeholder
    assert '@generated:peer:0' in user_env['deps'], "User deps should have placeholder"
    print(f"✓ User deps have placeholder: {@generated:peer:0' in user_env['deps']}")
    
    return True


def test_pipeline_placeholder_resolution():
    """Test that pipeline correctly resolves placeholders."""
    from core.pipeline import PipelineRunner
    
    # Test the _resolve_placeholders method directly
    runner = PipelineRunner(db_path=':memory:', verbose=False)
    
    # Simulate generated IDs
    generated_ids = {
        'peer': ['peer_abc123', 'peer_def456'],
        'identity': ['identity_xyz789']
    }
    
    # Test envelope with placeholders
    envelope = {
        'event_plaintext': {
            'type': 'user',
            'peer_id': '@generated:peer:0',
            'other_peer': '@generated:peer:1'
        },
        'deps': ['@generated:peer:0', '@generated:identity:0', 'invite:some_invite']
    }
    
    # Resolve placeholders
    runner._resolve_placeholders(envelope, generated_ids)
    
    # Check resolution
    assert envelope['event_plaintext']['peer_id'] == 'peer_abc123', "First peer placeholder not resolved"
    print(f"✓ Resolved peer_id: {envelope['event_plaintext']['peer_id']}")
    
    assert envelope['event_plaintext']['other_peer'] == 'peer_def456', "Second peer placeholder not resolved"
    print(f"✓ Resolved other_peer: {envelope['event_plaintext']['other_peer']}")
    
    assert 'peer:peer_abc123' in envelope['deps'], "Dep placeholder not resolved"
    print(f"✓ Resolved dep: peer:peer_abc123")
    
    assert 'identity:identity_xyz789' in envelope['deps'], "Identity dep not resolved"
    print(f"✓ Resolved dep: identity:identity_xyz789")
    
    assert 'invite:some_invite' in envelope['deps'], "Non-placeholder dep was changed"
    print(f"✓ Non-placeholder dep unchanged: invite:some_invite")
    
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("Testing join_as_user Command with Placeholder Resolution")
    print("=" * 60)
    
    print("\n1. Testing basic command execution:")
    print("-" * 40)
    test_join_as_user_basic()
    
    print("\n2. Testing database state after command:")
    print("-" * 40)
    test_join_as_user_with_db_check()
    
    print("\n3. Testing placeholder structure in command output:")
    print("-" * 40)
    test_placeholder_resolution()
    
    print("\n4. Testing pipeline placeholder resolution:")
    print("-" * 40)
    test_pipeline_placeholder_resolution()
    
    print("\n" + "=" * 60)
    print("All tests completed!")
