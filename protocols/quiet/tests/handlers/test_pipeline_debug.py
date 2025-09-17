#!/usr/bin/env python3
"""
Debug pipeline processing.
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from protocols.quiet.events.network.create import create_network
from core.pipeline import PipelineRunner
from core.handlers import registry
import tempfile

def test_pipeline_debug():
    """Debug why events aren't being processed."""
    # Create command envelopes
    params = {"name": "Test Network", "description": "Test"}
    envelopes = create_network(params)

    # Add request_id to track stored events
    import uuid
    request_id = str(uuid.uuid4())
    for env in envelopes:
        env['request_id'] = request_id

    print(f"Created {len(envelopes)} envelopes with request_id: {request_id}")
    for i, env in enumerate(envelopes):
        print(f"\nEnvelope {i}:")
        print(f"  Type: {env['event_type']}")
        print(f"  Self created: {env.get('self_created', False)}")
        print(f"  Event: {env['event_plaintext']['type']}")
        print(f"  Network ID in envelope: {env.get('network_id', 'NOT SET')}")
        print(f"  Network ID in event: {env['event_plaintext'].get('network_id', 'NOT SET')}")
    
    # Create pipeline runner
    with tempfile.NamedTemporaryFile(suffix='.db') as tmp:
        runner = PipelineRunner(db_path=tmp.name, verbose=True)

        print(f"\nRegistered handlers: {[h.name for h in registry._handlers]}")

        # Load handlers
        protocol_dir = Path(project_root) / "protocols" / "quiet"
        runner._load_protocol_handlers(str(protocol_dir))

        print(f"\nHandlers after loading: {[h.name for h in registry._handlers]}")

        # Process envelopes
        print("\n--- Processing envelopes ---")
        from core.db import get_connection, init_database
        db = get_connection(tmp.name)
        init_database(db, str(protocol_dir))
        result = runner._process_envelopes(envelopes, db)
        print(f"\n--- Result ---")
        print(f"Stored IDs: {result}")
        db.close()

if __name__ == "__main__":
    test_pipeline_debug()
