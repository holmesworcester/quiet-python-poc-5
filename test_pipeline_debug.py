#!/usr/bin/env python3
"""
Debug pipeline processing.
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from protocols.quiet.events.network.commands import create_network
from core.processor import PipelineRunner
from core.handler import registry
import tempfile

def test_pipeline_debug():
    """Debug why events aren't being processed."""
    # Create command envelopes
    params = {"name": "Test Network", "description": "Test"}
    envelopes = create_network(params)
    
    print(f"Created {len(envelopes)} envelopes")
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
        runner._process_envelopes(envelopes, runner.runner.db)

if __name__ == "__main__":
    test_pipeline_debug()