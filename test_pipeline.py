"""
Test script to demonstrate event flowing through the pipeline.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
import time
from core.envelope import Envelope
from core.handler import registry
from core.database import get_connection, init_database
from core.crypto import generate_keypair, sign, encrypt, hash

# Import handlers
from protocols.quiet.handlers.receive_from_network import ReceiveFromNetworkHandler
from protocols.quiet.handlers.resolve_deps import ResolveDepsHandler
from protocols.quiet.handlers.decrypt_transit import DecryptTransitHandler
from protocols.quiet.handlers.decrypt_event import DecryptEventHandler
from protocols.quiet.handlers.check_sig import CheckSigHandler
from protocols.quiet.handlers.validate import ValidateHandler
from protocols.quiet.handlers.project import ProjectHandler

# Import event types
from protocols.quiet.event_types.identity import IdentityEventType


def setup_handlers():
    """Register all handlers in order."""
    registry.register(ReceiveFromNetworkHandler())
    registry.register(DecryptTransitHandler())
    registry.register(DecryptEventHandler())
    registry.register(ResolveDepsHandler())
    registry.register(CheckSigHandler())
    registry.register(ValidateHandler())
    registry.register(ProjectHandler())


def create_test_identity():
    """Create a test identity event."""
    identity_data = IdentityEventType.create({
        'network_id': 'test-network-001'
    })
    return identity_data


def simulate_network_receive(event_data: dict, transit_key: bytes, transit_key_id: str) -> Envelope:
    """Simulate receiving an event over the network."""
    
    # Prepare event for transit
    transit_payload = {
        'event_key_id': None,  # No event-layer encryption for identity
        'event_ciphertext': json.dumps(event_data).encode().hex()
    }
    
    # Encrypt for transit
    plaintext = json.dumps(transit_payload).encode()
    ciphertext, nonce = encrypt(plaintext, transit_key)
    
    # Create raw network data
    raw_data = bytes.fromhex(transit_key_id) + nonce + ciphertext
    
    # Create initial envelope
    envelope = Envelope(
        origin_ip='127.0.0.1',
        origin_port=8080,
        received_at=int(time.time() * 1000),
        raw_data=raw_data
    )
    
    return envelope


def main():
    """Run the pipeline test."""
    print("=== Quiet Protocol Pipeline Test ===\n")
    
    # Setup database
    db = get_connection(':memory:')
    init_database(db)
    
    # Setup handlers
    setup_handlers()
    print("✓ Handlers registered\n")
    
    # Create transit key
    from core.crypto import generate_secret
    transit_key = generate_secret()
    transit_key_id = hash(transit_key, 32).hex()
    
    # Store transit key in database
    db.execute("""
        INSERT INTO transit_keys (key_id, network_id, secret, created_at)
        VALUES (?, ?, ?, ?)
    """, (transit_key_id, 'test-network-001', transit_key, int(time.time() * 1000)))
    db.commit()
    print(f"✓ Transit key created: {transit_key_id[:16]}...\n")
    
    # Create identity event
    identity_data = create_test_identity()
    event = identity_data['event']
    private_key = identity_data['private_key']
    print(f"✓ Identity event created:")
    print(f"  - Type: {event['type']}")
    print(f"  - Peer ID: {event['peer_id'][:16]}...")
    print(f"  - Network: {event['network_id']}\n")
    
    # Simulate network receive
    envelope = simulate_network_receive(event, transit_key, transit_key_id)
    print("✓ Simulated network receive\n")
    
    # Process through pipeline
    print("=== Processing through pipeline ===\n")
    
    # Keep processing until no more envelopes
    envelopes_to_process = [envelope]
    processed = []
    iteration = 0
    
    while envelopes_to_process and iteration < 10:
        iteration += 1
        print(f"--- Iteration {iteration} ---")
        
        next_batch = []
        for env in envelopes_to_process:
            print(f"\nProcessing: {env}")
            emitted = registry.process_envelope(env, db)
            next_batch.extend(emitted)
            processed.append(env)
        
        envelopes_to_process = next_batch
    
    print(f"\n=== Pipeline Complete ===")
    print(f"Total iterations: {iteration}")
    print(f"Total envelopes processed: {len(processed)}")
    
    # Check final state
    print("\n=== Final State ===")
    
    # Check events table
    cursor = db.execute("SELECT * FROM events")
    events = cursor.fetchall()
    print(f"\nStored events: {len(events)}")
    for event in events:
        print(f"  - {event['event_type']}: {event['event_id'][:16]}...")
    
    # Check peers table
    cursor = db.execute("SELECT * FROM peers")
    peers = cursor.fetchall()
    print(f"\nKnown peers: {len(peers)}")
    for peer in peers:
        print(f"  - {peer['peer_id'][:16]}... on {peer['network_id']}")
    
    # Check for any blocked events
    cursor = db.execute("SELECT COUNT(*) as count FROM blocked_events")
    blocked_count = cursor.fetchone()['count']
    print(f"\nBlocked events: {blocked_count}")


if __name__ == '__main__':
    main()