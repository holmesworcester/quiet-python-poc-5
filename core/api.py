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
from .jobs import JobScheduler


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

        # Initialize job scheduler
        self.scheduler = JobScheduler(
            db_path=str(self.db_path)
        )
        
        # Load OpenAPI spec if present (optional)
        openapi_path = self.protocol_dir / "openapi.yaml"
        self.openapi = {}
        self._specless = False
        if openapi_path.exists():
            with open(openapi_path, 'r') as f:
                self.openapi = yaml.safe_load(f)
            # Parse operations from OpenAPI spec
            self._parse_operations()
        else:
            # No spec: operate in discovery-only mode
            self._specless = True
            self.operations = {}

        # Discover and register implementations
        self._discover_implementations()

        # If running without a spec, synthesize operation map from registries
        if self._specless:
            self._synthesize_operations_from_registries()
        else:
            # Validate all operations have implementations
            self._validate_operations()
    
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
    
    def _validate_operations(self) -> None:
        """Validate that all operations have corresponding implementations."""
        from core.commands import command_registry

        missing_implementations = []

        for operation_id, operation in self.operations.items():
            # Check based on operation ID format
            if operation_id.startswith('core.'):
                # Core operations - verify they exist dynamically
                core_op = operation_id.replace('core.', 'core_')
                if not self._has_core_operation(core_op):
                    missing_implementations.append((operation_id, 'core_command'))

            elif operation['method'] == 'post':
                # Should be a command
                if not command_registry.has_command(operation_id):
                    missing_implementations.append((operation_id, 'command'))

            elif operation['method'] == 'get':
                # Should be a query
                if not self.query_registry.has_query(operation_id):
                    missing_implementations.append((operation_id, 'query'))

        if missing_implementations:
            error_msg = "Missing implementations for the following operation IDs:\n"
            for op_id, impl_type in missing_implementations:
                error_msg += f"  - {op_id} ({impl_type})\n"
            raise ValueError(error_msg)

    def _has_core_operation(self, core_op: str) -> bool:
        """Check if a core operation exists by trying to import it."""
        try:
            # Dynamically check for core operations
            from core import identity
            return hasattr(identity, core_op)
        except ImportError:
            return False

    def _discover_implementations(self) -> None:
        """Discover command and query implementations for operations."""
        import sys
        import importlib
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

        # Prepare type index
        self.type_index: Dict[str, Dict[str, Any]] = {}

        # Discover commands from event directories
        events_dir = self.protocol_dir / "events"
        if events_dir.exists():
            for event_dir in events_dir.iterdir():
                if not event_dir.is_dir() or event_dir.name.startswith('_'):
                    continue

                event_type = event_dir.name
                commands_file = event_dir / 'commands.py'

                if commands_file.exists():
                    try:
                        # Import the commands module
                        module_name = f'protocols.{self.protocol_dir.name}.events.{event_type}.commands'
                        module = importlib.import_module(module_name)

                        # Find all command functions
                        import inspect
                        for name in dir(module):
                            obj = getattr(module, name)
                            if callable(obj) and hasattr(obj, '_is_command'):
                                # Register with event_type.function_name format
                                func_name = getattr(obj, '_original_name', name)

                                # Simple consistent mapping: event_type.function_name
                                operation_id = f'{event_type}.{func_name}'
                                command_registry.register(operation_id, obj)

                                # Capture optional type metadata
                                param_t = getattr(obj, '_param_type', None)
                                result_t = getattr(obj, '_result_type', None)
                                if param_t is not None or result_t is not None:
                                    self.type_index[operation_id] = {
                                        'params': param_t,
                                        'result': result_t
                                    }

                                # Also register response handlers if they exist
                                response_func_name = f'{func_name}_response'
                                if hasattr(module, response_func_name):
                                    response_func = getattr(module, response_func_name)
                                    command_registry.register_response_handler(operation_id, response_func)

                    except ImportError as e:
                        # Module couldn't be imported, skip it
                        pass

                # Also inspect queries for type metadata (registration handled by query_registry)
                queries_file = event_dir / 'queries.py'
                if queries_file.exists():
                    try:
                        q_module_name = f'protocols.{self.protocol_dir.name}.events.{event_type}.queries'
                        q_module = importlib.import_module(q_module_name)
                        import inspect as _inspect
                        for qname in dir(q_module):
                            qobj = getattr(q_module, qname)
                            if callable(qobj) and hasattr(qobj, '_is_query'):
                                op_id = f'{event_type}.{qname}'
                                param_t = getattr(qobj, '_param_type', None)
                                result_t = getattr(qobj, '_result_type', None)
                                if param_t is not None or result_t is not None:
                                    self.type_index[op_id] = {
                                        'params': param_t,
                                        'result': result_t
                                    }
                    except ImportError:
                        pass

    def _synthesize_operations_from_registries(self) -> None:
        """When no OpenAPI spec is present, derive an operation map from registries.

        - Commands => method post
        - Queries  => method get
        """
        from core.commands import command_registry
        from core.queries import query_registry

        ops: Dict[str, Dict[str, object]] = {}

        for op in command_registry.list_commands():
            ops[op] = {
                'path': f'/{op.split(".", 1)[0]}',
                'method': 'post',
                'spec': {}
            }

        for op in query_registry.list_queries():
            # avoid overwriting if same id appears in both (shouldn't)
            if op not in ops:
                ops[op] = {
                    'path': f'/{op.split(".", 1)[0]}s',
                    'method': 'get',
                    'spec': {}
                }

        self.operations = ops
    
    def execute_operation(self, operation_id: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Execute an operation by its OpenAPI operation ID."""
        # Check if this starts with 'core.' for core operations
        if operation_id.startswith('core.'):
            # Map to internal core function names
            core_op = operation_id.replace('core.', 'core_')
            return self._execute_core_command(core_op, params)

        # In specless mode or if operation not parsed from spec, fall back to registries
        if operation_id not in self.operations:
            from core.commands import command_registry
            from core.queries import query_registry
            if command_registry.has_command(operation_id):
                return self._execute_command(operation_id, params)
            if query_registry.has_query(operation_id):
                return self._execute_query(operation_id, params)
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
                from typing import Dict as _Dict, Any as _Any, cast as _cast
                return _cast(_Dict[str, _Any], response_handler(stored_ids, params or {}, db))
            else:
                # Fallback to standard response with just IDs
                return {
                    "ids": stored_ids,
                    "data": {}
                }
            
        finally:
            db.close()

    def _execute_core_command(self, operation_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a core framework command (not through pipeline)."""
        # Dynamically import and execute core commands
        try:
            from core import identity

            if hasattr(identity, operation_id):
                from typing import Dict as _Dict, Any as _Any, Callable as _Callable, cast as _cast
                func = getattr(identity, operation_id)
                # Execute the core command directly with db_path
                return _cast(_Dict[str, _Any], func(params or {}, str(self.db_path)))
            else:
                raise ValueError(f"Unknown core command: {operation_id}")

        except ImportError:
            raise ValueError(f"Core module not available for: {operation_id}")

    def _execute_query(self, operation_id: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Execute a query."""
        # Get database connection
        db = get_connection(str(self.db_path))

        try:
            # Operation IDs for queries already use the event_type.function format
            # Just execute directly through the registry
            result = self.query_registry.execute(operation_id, params or {}, db)
            return result

        finally:
            db.close()

    def tick_scheduler(self) -> int:
        """
        Check for due jobs and process any run_job envelopes.

        Returns:
            Number of jobs triggered
        """
        # Get run_job envelopes from scheduler
        envelopes = self.scheduler.tick()

        if envelopes:
            # Process the run_job envelopes through the pipeline
            db = get_connection(str(self.db_path))
            try:
                self.runner.run(
                    protocol_dir=str(self.protocol_dir),
                    input_envelopes=envelopes,
                    db=db
                )
            finally:
                db.close()

        return len(envelopes)
    
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

    # ---------------------------------------------------------------------
    # Debug/Introspection helpers
    # ---------------------------------------------------------------------
    def dump_database(self, limit_per_table: int | None = None) -> dict[str, list[dict[str, Any]]]:
        """
        Return a raw dump of key tables for inspection.

        Args:
            limit_per_table: Optional cap on number of rows returned per table.

        Returns:
            Mapping of table name -> list of row dicts.
        """
        import sqlite3 as _sqlite3

        tables_to_dump = [
            "core_identities",
            "peers",
            "users",
            "groups",
            "group_members",
            "channels",
            "messages",
            "events",
            "projected_events",
            "blocked_events",
        ]

        result: dict[str, list[dict[str, Any]]] = {}

        conn = get_connection(str(self.db_path))
        try:
            conn.row_factory = _sqlite3.Row
            cur = conn.cursor()

            for table in tables_to_dump:
                # Check table exists
                cur.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
                    (table,)
                )
                if cur.fetchone() is None:
                    result[table] = []
                    continue

                # Special ordering for certain tables
                order_by = None
                if table == "events":
                    # event store recency
                    order_by = "received_at DESC"
                elif table == "messages":
                    order_by = "created_at DESC"
                elif table in ("groups", "channels", "users", "peers", "core_identities"):
                    # best-effort chronological ordering if timestamp column exists
                    # will fallback below if column missing
                    order_by = "created_at DESC"

                query = f"SELECT * FROM {table}"
                if order_by:
                    # Verify the column exists before adding ORDER BY
                    try:
                        cur.execute(f"PRAGMA table_info({table})")
                        cols = {r[1] for r in cur.fetchall()}
                        if any(col in cols for col in [c.strip().split()[0] for c in order_by.split(',')]):
                            query += f" ORDER BY {order_by}"
                    except Exception:
                        pass

                if limit_per_table is not None and isinstance(limit_per_table, int) and limit_per_table > 0:
                    query += f" LIMIT {limit_per_table}"

                cur.execute(query)
                rows = cur.fetchall()
                result[table] = [dict(r) for r in rows]

        finally:
            conn.close()

        return result


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
