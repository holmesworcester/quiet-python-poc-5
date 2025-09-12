"""
Protocol API client - protocol-agnostic client that uses OpenAPI spec.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
import sqlite3

from .processor import PipelineRunner
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
    
    def _parse_operations(self):
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
    
    def _discover_implementations(self):
        """Discover command and query implementations for operations."""
        import sys
        protocol_root = self.protocol_dir.parent.parent
        if str(protocol_root) not in sys.path:
            sys.path.insert(0, str(protocol_root))
        
        # Import registries
        from core.processor import command_registry
        from core.query import query_registry
        
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
                                # Register as query if it has the query marker
                                if getattr(func, '_is_query', False):
                                    query_registry.register(operation_id, func)
                
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
        """Execute a command through the pipeline runner."""
        from core.processor import command_registry
        
        # Get database connection
        db = get_connection(str(self.db_path))
        
        try:
            # Execute command through registry
            envelopes = command_registry.execute(operation_id, params or {}, db)
            
            # Run the pipeline to process the envelopes
            if envelopes:
                self.runner.run(
                    protocol_dir=str(self.protocol_dir),
                    input_envelopes=envelopes
                )
            
            # Extract result data from the first envelope
            result_data = {}
            if envelopes:
                env = envelopes[0]
                if 'event_plaintext' in env:
                    result_data = env['event_plaintext']
                else:
                    result_data = env
            
            return result_data
            
        finally:
            db.close()
    
    def _execute_query(self, operation_id: str, params: Dict[str, Any] = None) -> Any:
        """Execute a query."""
        from core.query import query_registry
        
        # Get database connection
        db = get_connection(str(self.db_path))
        
        try:
            # Execute query through registry using operation_id
            result = query_registry.execute(operation_id, db, params or {})
            return result
            
        finally:
            db.close()
    
    def __getattr__(self, name: str):
        """Dynamic method creation for OpenAPI operations."""
        # Check if this is an operation from OpenAPI spec
        if name in self.operations:
            def operation_method(*args, **kwargs):
                # Handle both positional and keyword arguments
                if args and not kwargs:
                    # Check the OpenAPI spec to determine parameter names
                    spec = self.operations[name]['spec']
                    if 'requestBody' in spec:
                        schema = spec['requestBody']['content']['application/json']['schema']
                        required = schema.get('required', [])
                        
                        # If single required parameter and single argument, map it
                        if len(required) == 1 and len(args) == 1:
                            param_name = required[0]
                            return self.execute_operation(name, {param_name: args[0]})
                    
                    # Otherwise assume it's a params dict
                    return self.execute_operation(name, args[0] if isinstance(args[0], dict) else None)
                else:
                    return self.execute_operation(name, kwargs if kwargs else None)
            return operation_method
        
        # If not found, raise AttributeError
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")


class APIError(Exception):
    """API error with status code."""
    
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"API Error {status_code}: {message}")


# For backward compatibility
APIClient = API