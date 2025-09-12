"""
Direct API client for protocols - no HTTP, just function calls.
Following poc-3's pattern of direct execution.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
import sqlite3

from .processor import PipelineRunner


class APIClient:
    """Direct API client for protocols using function calls instead of HTTP."""
    
    def __init__(self, protocol_dir: str = None, reset_db: bool = True):
        """
        Initialize API client with direct pipeline access.
        
        Args:
            protocol_dir: Protocol directory path (defaults to current protocol)
            reset_db: Whether to reset database on init
        """
        # Determine protocol directory
        if protocol_dir:
            self.protocol_dir = Path(protocol_dir)
        else:
            # Try to infer from current working directory
            cwd = Path.cwd()
            if (cwd / "openapi.yaml").exists():
                self.protocol_dir = cwd
            else:
                # Default to quiet protocol
                self.protocol_dir = Path(__file__).parent.parent / "protocols" / "quiet"
        
        # Database path
        self.db_path = self.protocol_dir / "demo.db"
        
        # Reset database if requested
        if reset_db and self.db_path.exists():
            import os
            os.remove(self.db_path)
        
        # Initialize pipeline runner
        self.runner = PipelineRunner(
            db_path=str(self.db_path),
            verbose=False
        )
        
        # Load OpenAPI spec to understand operation mappings
        openapi_path = self.protocol_dir / "openapi.yaml"
        if openapi_path.exists():
            import yaml
            with open(openapi_path, 'r') as f:
                self.openapi = yaml.safe_load(f)
        else:
            self.openapi = None
    
    def _register_commands(self):
        """Register all commands from event type directories."""
        import sys
        protocol_root = self.protocol_dir.parent.parent
        if str(protocol_root) not in sys.path:
            sys.path.insert(0, str(protocol_root))
        
        # Find all event directories
        events_dir = self.protocol_dir / "events"
        if not events_dir.exists():
            return
        
        # Import command_registry
        from core.processor import command_registry
        
        # For each event type directory
        for event_dir in events_dir.iterdir():
            if event_dir.is_dir() and (event_dir / "commands.py").exists():
                try:
                    # Import the commands module
                    import importlib
                    module_path = f'protocols.{self.protocol_dir.name}.events.{event_dir.name}.commands'
                    commands_module = importlib.import_module(module_path)
                    
                    # Register each command function
                    for attr_name in dir(commands_module):
                        if attr_name.startswith('create_') or attr_name == 'join_network':
                            command_func = getattr(commands_module, attr_name)
                            if callable(command_func):
                                command_registry.register(attr_name, command_func)
                except ImportError as e:
                    print(f"Failed to import commands from {event_dir.name}: {e}")
        
        # Register system commands
        from core.types import Envelope
        def system_dump_database(params: Dict[str, Any]) -> Envelope:
            """System command to dump database - returns empty envelope."""
            return {
                'event_plaintext': {},
                'event_type': 'system',
                'self_created': True,
                'deps': []
            }
        
        command_registry.register("system.dump_database", system_dump_database)
    
    def _execute_command(self, operation_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a command through the pipeline runner."""
        try:
            # Ensure commands are registered
            self._register_commands()
            
            # Get database connection
            from core.database import get_connection, init_database
            db = get_connection(str(self.db_path))
            init_database(db, str(self.protocol_dir))
            
            # Keep connection open for queries
            self._db = db
            
            # Map operation IDs to actual command names  
            command_map = {
                "identity.create": "create_identity",
                "key.create": "create_key",
                "transit_secret.create": "create_transit_secret"
            }
            
            cmd_name = command_map.get(operation_id, operation_id)
            
            # Execute command directly through registry
            from core.processor import command_registry
            envelopes = command_registry.execute(cmd_name, params or {}, db)
            
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
            
            return {
                "success": True,
                "data": result_data
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _register_queries(self):
        """Register all queries from event type directories."""
        import sys
        protocol_root = self.protocol_dir.parent.parent
        if str(protocol_root) not in sys.path:
            sys.path.insert(0, str(protocol_root))
        
        # Find all event directories
        events_dir = self.protocol_dir / "events"
        if not events_dir.exists():
            return
        
        # Import query_registry
        from core.queries import query_registry
        
        # For each event type directory
        for event_dir in events_dir.iterdir():
            if event_dir.is_dir() and (event_dir / "queries.py").exists():
                try:
                    # Import the queries module
                    import importlib
                    module_path = f'protocols.{self.protocol_dir.name}.events.{event_dir.name}.queries'
                    queries_module = importlib.import_module(module_path)
                    
                    # Register each query function
                    for attr_name in dir(queries_module):
                        if attr_name.startswith('list_') or attr_name.startswith('get_'):
                            query_func = getattr(queries_module, attr_name)
                            if callable(query_func):
                                query_registry.register(attr_name, query_func)
                except ImportError as e:
                    print(f"Failed to import queries from {event_dir.name}: {e}")
        
        # Register system queries
        from core.queries_system import dump_database, get_logs
        query_registry.register("dump_database", dump_database)
        query_registry.register("get_processor_logs", get_logs)
    
    def _execute_query(self, operation_id: str, params: Dict[str, Any] = None) -> Any:
        """Execute a query through the query registry."""
        try:
            # Ensure queries are registered
            self._register_queries()
            
            # Get database connection
            from core.database import get_connection
            db = get_connection(str(self.db_path))
            
            # Execute query through registry
            from core.queries import query_registry
            result = query_registry.execute(operation_id, params or {}, db)
            
            return result
                
        except Exception as e:
            raise APIError(500, str(e))
    
    # Identity Management
    
    def create_identity(self, network_id: str) -> Dict[str, Any]:
        """Create a new identity."""
        result = self._execute_command("identity.create", {"network_id": network_id})
        if not result["success"]:
            raise APIError(500, result.get("error", "Failed to create identity"))
        # Return the identity data in the expected format
        data = result["data"]
        return {
            "identity_id": data.get("peer_id"),
            "network_id": data.get("network_id"),
            "created_at": data.get("created_at")
        }
    
    def list_identities(self) -> list:
        """List all identities."""
        return self._execute_query("identity.list", {})
    
    # Key Management
    
    def create_key(self, group_id: str, network_id: str, identity_id: str) -> Dict[str, Any]:
        """Create a new encryption key for a group."""
        result = self._execute_command("key.create", {
            "group_id": group_id,
            "network_id": network_id,
            "identity_id": identity_id
        })
        if not result["success"]:
            raise APIError(500, result.get("error", "Failed to create key"))
        return result["data"]
    
    def list_keys(self, group_id: Optional[str] = None) -> list:
        """List all keys, optionally filtered by group."""
        params = {}
        if group_id:
            params["group_id"] = group_id
        return self._execute_query("key.list", params)
    
    # Transit Key Management
    
    def create_transit_secret(self, network_id: str, identity_id: str) -> Dict[str, Any]:
        """Create a new transit encryption key."""
        result = self._execute_command("transit_secret.create", {
            "network_id": network_id,
            "identity_id": identity_id
        })
        if not result["success"]:
            raise APIError(500, result.get("error", "Failed to create transit secret"))
        return result["data"]
    
    def list_transit_keys(self, network_id: Optional[str] = None) -> list:
        """List all transit keys, optionally filtered by network."""
        params = {}
        if network_id:
            params["network_id"] = network_id
        return self._execute_query("transit_secret.list", params)
    
    # System Functions
    
    def dump_database(self) -> Dict[str, Any]:
        """Get current database state."""
        return self._execute_query("dump_database", {})
    
    def get_processor_logs(self, limit: int = 100) -> list:
        """Get recent processor logs."""
        return self._execute_query("get_processor_logs", {"limit": limit})


class APIError(Exception):
    """API error with status code."""
    
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"API Error {status_code}: {message}")