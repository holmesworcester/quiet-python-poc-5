#!/usr/bin/env python3
"""
Complete integration test that simulates full pipeline processing.
"""
import sys
import tempfile
import hashlib
import json
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.api import API
from core.db import get_connection
from protocols.quiet.events.network.commands import create_network

def test_network_creation_full():
    """Test network creation with manual pipeline simulation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        protocol_dir = Path(project_root) / "protocols" / "quiet"
        
        print("1. Creating network command...")
        params = {"name": "Test Network", "description": "Test"}
        envelopes = create_network(params)
        
        print(f"   Generated {len(envelopes)} envelopes")
        
        # Manually simulate what the missing handlers would do
        processed_envelopes = []
        
        for i, env in enumerate(envelopes):
            print(f"\n2. Processing envelope {i} ({env['event_type']})...")
            
            # Simulate signature handler - generate event_id
            event_plaintext = env['event_plaintext']
            canonical = json.dumps(event_plaintext, sort_keys=True).encode()
            event_id = hashlib.blake2b(canonical).hexdigest()
            
            # For network events, use event_id as network_id
            if event_plaintext['type'] == 'network':
                event_plaintext['network_id'] = event_id
                env['network_id'] = event_id
            elif event_plaintext['type'] == 'identity':
                # Identity needs the network_id from the network event
                if processed_envelopes:
                    network_env = processed_envelopes[0]
                    network_id = network_env['network_id']
                    event_plaintext['network_id'] = network_id
                    env['network_id'] = network_id
            
            # Add fields that handlers would add
            env['event_id'] = event_id
            env['sig_checked'] = True
            env['validated'] = True
            env['projected'] = False
            
            processed_envelopes.append(env)
            
            print(f"   Event ID: {event_id[:16]}...")
            print(f"   Network ID: {env.get('network_id', 'N/A')[:16]}...")
        
        print("\n3. Running through API pipeline...")
        # Create API and run pipeline
        api = API(protocol_dir, reset_db=True, db_path=db_path)
        
        # Get the runner from API and process envelopes
        from core.pipeline import PipelineRunner
        runner = PipelineRunner(db_path=str(db_path), verbose=False)
        runner.run(
            protocol_dir=str(protocol_dir),
            input_envelopes=processed_envelopes
        )
        
        print("\n4. Checking database state...")
        db = get_connection(str(db_path))
        
        # Check networks table
        cursor = db.execute("SELECT * FROM networks")
        networks = cursor.fetchall()
        print(f"\nNetworks: {len(networks)}")
        for net in networks:
            print(f"  - {net['name']} (ID: {net['network_id'][:16]}...)")
        
        # Check identities
        cursor = db.execute("SELECT identity_id, name, network_id FROM identities")
        identities = cursor.fetchall()
        print(f"\nIdentities: {len(identities)}")
        for identity in identities:
            print(f"  - {identity['name']} (ID: {identity['identity_id'][:16]}...)")
        
        # Check peers
        cursor = db.execute("SELECT peer_id, network_id FROM peers")
        peers = cursor.fetchall()
        print(f"\nPeers: {len(peers)}")
        for peer in peers:
            print(f"  - Peer ID: {peer['peer_id'][:16]}...")
        
        db.close()
        
        # Verify results
        assert len(networks) == 1, f"Expected 1 network, got {len(networks)}"
        assert networks[0]['name'] == "Test Network"
        
        print("\n✓ Test passed!")

if __name__ == "__main__":
    test_network_creation_full()