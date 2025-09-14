#!/usr/bin/env python3
"""
Simple integration test to debug pipeline processing.
"""
import sys
import tempfile
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.api import API
from core.db import get_connection

def test_create_network_simple():
    """Test creating a network through the full pipeline."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        protocol_dir = Path(project_root) / "protocols" / "quiet"
        
        # Create API client
        print("Creating API client...")
        api = API(protocol_dir, reset_db=True, db_path=db_path)
        
        # Create network
        print("\nCalling create_network...")
        result = api.create_network(name="Test Network", description="Test description")
        
        print(f"\nAPI Result: {json.dumps(result, indent=2)}")
        
        # Check database state
        print("\nChecking database state...")
        db = get_connection(str(db_path))
        
        # First check what tables exist
        cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = cursor.fetchall()
        print(f"\nTables in database: {[t['name'] for t in tables]}")
        
        # Check events table
        if any(t['name'] == 'events' for t in tables):
            cursor = db.execute("SELECT event_id, event_type FROM events")
            events = cursor.fetchall()
            print(f"\nEvents in database: {len(events)}")
            for event in events:
                print(f"  - {event['event_type']}: {event['event_id']}")
        
        # Check networks projection
        if any(t['name'] == 'networks' for t in tables):
            cursor = db.execute("SELECT * FROM networks")
            networks = cursor.fetchall()
            print(f"\nNetworks in database: {len(networks)}")
            for network in networks:
                print(f"  - {dict(network)}")
        
        # Check identities
        if any(t['name'] == 'identities' for t in tables):
            cursor = db.execute("SELECT * FROM identities")
            identities = cursor.fetchall()
            print(f"\nIdentities in database: {len(identities)}")
            for identity in identities:
                # Don't print private key
                identity_dict = dict(identity)
                if 'private_key' in identity_dict:
                    identity_dict['private_key'] = '<hidden>'
                print(f"  - {identity_dict}")
        
        # Check peers
        if any(t['name'] == 'peers' for t in tables):
            cursor = db.execute("SELECT * FROM peers")
            peers = cursor.fetchall()
            print(f"\nPeers in database: {len(peers)}")
            for peer in peers:
                print(f"  - {dict(peer)}")
        
        db.close()

if __name__ == "__main__":
    test_create_network_simple()