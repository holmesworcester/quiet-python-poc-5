#!/usr/bin/env python3
"""Simple test of handler integration."""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from core.processor import PipelineRunner
from core.db import get_connection, init_database
from protocols.quiet.handlers import (
    event_crypto_handler,
    signature_handler,
    transit_crypto_handler,
    membership_check_handler,
    check_outgoing_handler,
    event_store_handler,
    remove_handler,
    resolve_deps_handler,
    send_to_network_handler,
    project,
    validate
)
import tempfile
import sqlite3

def test_handlers():
    """Test handler instantiation and basic filtering."""
    # Create temp database
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test.db")
    protocol_dir = "/home/hwilson/quiet-python-poc-5/protocols/quiet"
    
    # Setup database
    db = get_connection(db_path)
    init_database(db, protocol_dir)
    
    # Test creating handler instances
    handlers = [
        event_crypto_handler.EventCryptoHandler(),
        signature_handler.SignatureHandler(),
        transit_crypto_handler.TransitCryptoHandler(),
        membership_check_handler.MembershipCheckHandler(),
        check_outgoing_handler.CheckOutgoingHandler(),
        event_store_handler.EventStoreHandler(),
        remove_handler.RemoveHandler(),
        resolve_deps_handler.ResolveDepsHandler(),
        send_to_network_handler.SendToNetworkHandler(),
    ]
    
    print(f"Created {len(handlers)} handlers")
    
    # Test each handler's filter with a simple envelope
    test_envelope = {
        'event_type': 'test',
        'event_id': 'test123'
    }
    
    for handler in handlers:
        print(f"\nTesting {handler.name}:")
        print(f"  Filter result: {handler.filter(test_envelope)}")
    
    # Test a handler that should accept self_created events
    identity_envelope = {
        'event_type': 'identity',
        'self_created': True,
        'event_plaintext': {'type': 'identity'}
    }
    
    print("\nTesting with identity envelope:")
    for handler in handlers:
        if handler.filter(identity_envelope):
            print(f"  {handler.name} accepts identity envelope")
    
    print("\nAll handlers created successfully!")

if __name__ == "__main__":
    test_handlers()