#!/usr/bin/env python3
"""Minimal integration test to debug pipeline issues."""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import tempfile
import time
from core.pipeline import PipelineRunner
from protocols.quiet.events.network.commands import create_network

def main():
    """Run minimal integration test."""
    print("1. Creating network command...")
    params = {
        'name': 'Test Network',
        'description': 'Test network for integration testing',
        'creator_name': 'Test Admin'
    }
    envelopes = create_network(params)
    print(f"   Generated {len(envelopes)} envelopes")
    
    # Create temp directory for database
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test.db")
    protocol_dir = os.path.abspath("protocols/quiet")
    
    print(f"\n2. Running pipeline...")
    print(f"   Database: {db_path}")
    print(f"   Protocol: {protocol_dir}")
    
    # Run without verbose mode first
    runner = PipelineRunner(db_path=str(db_path), verbose=False)
    
    # Add timeout handling
    import signal
    
    def timeout_handler(signum, frame):
        print("\n\nTIMEOUT: Pipeline appears to be stuck!")
        sys.exit(1)
    
    # Set 10 second timeout
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(10)
    
    try:
        runner.run(protocol_dir=protocol_dir, input_envelopes=envelopes)
        signal.alarm(0)  # Cancel timeout
        print("\n3. Pipeline completed successfully!")
    except Exception as e:
        signal.alarm(0)  # Cancel timeout
        print(f"\n3. Pipeline failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()