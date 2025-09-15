"""
Protocol API client - protocol-agnostic client that uses OpenAPI spec.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
import sqlite3

from .pipeline import PipelineRunner
from .db import get_connection, init_database


class API:
    """Protocol API client using OpenAPI spec for operation discovery."""
    
    def __init__(self, protocol_dir: Path, reset_db: bool = True, db_path: Optional[Path] = None):
        """
        Initialize API client.
        
        Args:
            protocol_dir: Protocol directory path containing openapi.yaml
            reset_db: Whether to reset database on init
            db_path: Custom database path (defaults to protocol_dir/demo.db)
        """
        self.protocol_dir = Path(protocol_dir)
        
        # Database path
        self.db_path = db_path if db_path else self.protocol_dir / "demo.db"
        
        # Reset database if requested
        if reset_db and self.db_path.exists():
            os.remove(self.db_path)
        
        # Initialize database with protocol schema
        db = get_connection(str(self.db_path))
        init_database(db, str(self.protocol_dir))
        db.close()
        
        # Initialize pipeline runner
        self.runner = PipelineRunner(
            db_path=str(self.db_path),
            verbose=False
        )
        
        # Load OpenAPI spec
        openapi_path = self.protocol_dir / "openapi.yaml"
        if not openapi_path.exists():
            raise ValueError(f"No OpenAPI spec found at {openapi_path}")
        
        with open(openapi_path, 'r') as f:
            self.openapi = yaml.safe_load(f)
        
        # Parse operations from OpenAPI spec
        self._parse_operations()
        
        # Discover and register implementations
        self._discover_implementations()
    
    def _parse_operations(self) -> None:
        """Parse operations from OpenAPI spec."""
        self.operations = {}
        
        # Parse paths from OpenAPI
        for path, methods in self.openapi.get('paths', {}).items():
            for method, spec in methods.items():
                if 'operationId' in spec:
                    operation_id = spec['operationId']
                    self.operations[operation_id] = {
                        'path': path,
                        'method': method,
                        'spec': spec
                    }
    
    def _discover_implementations(self) -> None:
        """Discover command and query implementations for operations."""
        import sys
        protocol_root = self.protocol_dir.parent.parent
        if str(protocol_root) not in sys.path:
            sys.path.insert(0, str(protocol_root))
        
        # Import registries
        from core.commands import command_registry
        from core.queries import query_registry

        # Use the global query registry which has system queries
        self.query_registry = query_registry
        # Auto-discover protocol queries
        self.query_registry._auto_discover_queries(str(self.protocol_dir))
        
        # Protocol implementations could be organized in any way
        # We'll search for Python files that might contain implementations
        protocol_name = self.protocol_dir.name
        
        # Look for all Python files in the protocol directory
        for py_file in self.protocol_dir.rglob("*.py"):
            # Skip __pycache__ and test files
            if '__pycache__' in str(py_file) or 'test_' in py_file.name:
                continue
            
            # Convert file path to module path
            relative_path = py_file.relative_to(self.protocol_dir.parent.parent)
            module_parts = list(relative_path.parts[:-1]) + [relative_path.stem]
            module_path = '.'.join(module_parts)
            
            try:
                # Import the module
                module = __import__(module_path, fromlist=['*'])
                
                # Look for functions that match operation IDs
                for operation_id in self.operations:
                    if hasattr(module, operation_id):
                        func = getattr(module, operation_id)
                        if callable(func):
                            # Determine if it's a command or query based on method
                            operation = self.operations[operation_id]
                            if operation['method'] == 'post':
                                # Register as command if it has the command marker
                                if getattr(func, '_is_command', False):
                                    command_registry.register(operation_id, func)
                            elif operation['method'] == 'get':
                                # Queries are auto-discovered from the @query decorator
                                pass
                
            except ImportError:
                # Module couldn't be imported, skip it
                pass
    
    def execute_operation(self, operation_id: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Execute an operation by its OpenAPI operation ID."""
        if operation_id not in self.operations:
            raise ValueError(f"Unknown operation: {operation_id}")
        
        operation = self.operations[operation_id]
        
        if operation['method'] == 'post':
            # Execute as command
            return self._execute_command(operation_id, params)
        elif operation['method'] == 'get':
            # Execute as query
            return self._execute_query(operation_id, params)
        else:
            raise ValueError(f"Unsupported method: {operation['method']}")
    
    def _execute_command(self, operation_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a command through the pipeline runner and return standard response."""
        from core.commands import command_registry
        import uuid

        # Get database connection
        db = get_connection(str(self.db_path))

        try:
            # Generate request ID for tracking
            request_id = str(uuid.uuid4())

            # Execute command through registry
            envelopes = command_registry.execute(operation_id, params or {}, db)

            # Add request_id to all envelopes for tracking
            for envelope in envelopes:
                envelope['request_id'] = request_id

            # Run the pipeline to process the envelopes
            # Pipeline returns mapping of event_type -> event_id for stored events
            stored_ids = {}
            if envelopes:
                stored_ids = self.runner.run(
                    protocol_dir=str(self.protocol_dir),
                    input_envelopes=envelopes,
                    db=db  # Pass db so pipeline can track stored events
                )

            # Check if command has a response handler
            response_handler = command_registry.get_response_handler(operation_id)

            if response_handler:
                # Let the command shape its own response with query data
                return response_handler(stored_ids, params or {}, db)
            else:
                # Fallback to standard response with just IDs
                return {
                    "ids": stored_ids,
                    "data": {}
                }
            
        finally:
            db.close()
    
    def _execute_query(self, operation_id: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Execute a query."""
        # Get database connection
        db = get_connection(str(self.db_path))

        try:
            # Map OpenAPI operation IDs to query names
            # e.g., get_identities -> identity.get
            query_name = self._map_operation_to_query(operation_id)

            # Execute query through registry
            result = self.query_registry.execute(query_name, params or {}, db)
            return result

        finally:
            db.close()

    def _map_operation_to_query(self, operation_id: str) -> str:
        """Map OpenAPI operation ID to query name."""
        # Mapping rules:
        # get_identities -> identity.get
        # get_users -> user.get
        # list_keys -> key.list
        # etc.

        mappings = {
            'get_identities': 'identity.get',
            'get_users': 'user.get',
            'get_groups': 'group.get',
            'get_channels': 'channel.get',
            'get_messages': 'message.get',
            'list_keys': 'key.list',
            'list_transit_keys': 'transit_secret.list',
            'dump_database': 'system.dump_database',
            # Add more mappings as needed
        }

        return mappings.get(operation_id, operation_id)
    
    def __getattr__(self, name: str) -> Any:
        """Dynamic method creation for OpenAPI operations."""
        # Check if this is an operation from OpenAPI spec
        if name in self.operations:
            def operation_method(params: Optional[Dict[str, Any]] = None) -> Any:
                # Always expect a params dict
                return self.execute_operation(name, params)
            return operation_method
        
        # If not found, raise AttributeError
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")


# Alias for backwards compatibility
from typing import Type
APIClient: Type[API] = API


class APIError(Exception):
    """API error with status code."""
    
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"API Error {status_code}: {message}")


# For backward compatibility
APIClient = API