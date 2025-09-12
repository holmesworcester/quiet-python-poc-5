"""
Base class and utilities for scenario tests.
"""
import os
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
import pytest
import time

from core.api_client import APIClient, APIError


class ScenarioTestBase:
    """Base class for scenario tests with utilities."""
    
    def setup_method(self, method):
        """Set up test environment before each test."""
        # Create temporary directory for test databases
        self.temp_dir = tempfile.mkdtemp()
        self.clients: Dict[str, APIClient] = {}
        self.identities: Dict[str, Dict[str, Any]] = {}
    
    def teardown_method(self, method):
        """Clean up after each test."""
        # Close all clients
        for client in self.clients.values():
            if hasattr(client, '_db'):
                client._db.close()
        
        # Remove temporary directory
        shutil.rmtree(self.temp_dir)
    
    def create_client(self, name: str, reset_db: bool = True) -> APIClient:
        """Create a named API client instance."""
        # Use separate database for each client
        db_path = Path(self.temp_dir) / f"{name}.db"
        
        # Get protocol directory
        protocol_dir = Path(__file__).parent.parent.parent
        
        # Create client with specific database
        client = APIClient(protocol_dir=str(protocol_dir), reset_db=reset_db)
        client.db_path = db_path
        
        self.clients[name] = client
        return client
    
    def create_identity(self, client_name: str, network_id: str = "test-network") -> Dict[str, Any]:
        """Create an identity for a client and store it."""
        client = self.clients[client_name]
        identity = client.create_identity(network_id)
        self.identities[client_name] = identity
        return identity
    
    def wait_for_sync(self, timeout: float = 0.1):
        """Wait for events to propagate (simulated)."""
        time.sleep(timeout)
    
    def assert_event_exists(self, client_name: str, event_type: str, **filters) -> Dict[str, Any]:
        """Assert that an event exists in the client's database."""
        client = self.clients[client_name]
        db_state = client.dump_database()
        
        # Find events of the specified type
        events = []
        for table_name, rows in db_state.items():
            if table_name.endswith('_events') and event_type in table_name:
                events.extend(rows)
        
        # Apply filters
        matching_events = []
        for event in events:
            match = True
            for key, value in filters.items():
                if key not in event or event[key] != value:
                    match = False
                    break
            if match:
                matching_events.append(event)
        
        assert len(matching_events) > 0, f"No {event_type} event found with filters {filters}"
        return matching_events[0]
    
    def assert_no_event(self, client_name: str, event_type: str, **filters):
        """Assert that no event exists matching the criteria."""
        client = self.clients[client_name]
        db_state = client.dump_database()
        
        # Find events of the specified type
        events = []
        for table_name, rows in db_state.items():
            if table_name.endswith('_events') and event_type in table_name:
                events.extend(rows)
        
        # Apply filters
        for event in events:
            match = True
            for key, value in filters.items():
                if key not in event or event[key] != value:
                    match = False
                    break
            if match:
                pytest.fail(f"Found {event_type} event with filters {filters}, but expected none")
    
    def get_events_by_type(self, client_name: str, event_type: str) -> List[Dict[str, Any]]:
        """Get all events of a specific type from client's database."""
        client = self.clients[client_name]
        db_state = client.dump_database()
        
        events = []
        for table_name, rows in db_state.items():
            if table_name.endswith('_events') and event_type in table_name:
                events.extend(rows)
        
        return events
    
    def share_event(self, from_client: str, to_client: str, event: Dict[str, Any]):
        """Simulate sharing an event from one client to another."""
        # In a real implementation, this would go through the network
        # For now, we'll directly insert into the receiving client's pipeline
        receiver = self.clients[to_client]
        
        # Create envelope for the event
        envelope = {
            'event_plaintext': event,
            'event_type': event.get('type'),
            'self_created': False,
            'deps': event.get('deps', [])
        }
        
        # Process through the receiver's pipeline
        receiver.runner.run(
            protocol_dir=str(receiver.protocol_dir),
            input_envelopes=[envelope]
        )