"""
Production pipeline runner for processing envelopes through handlers.
Supports verbose logging and database inspection.
"""
import importlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Any, Optional

from .commands import command_registry
from .db import get_connection, init_database
from .handlers import registry


class PipelineRunner:
    """Production pipeline runner with configurable logging."""
    
    def __init__(self, db_path: str = "quiet.db", verbose: bool = False):
        self.db_path = db_path
        self.verbose = verbose
        self.processed_count = 0
        self.emitted_count = 0
        self.start_time = time.time()
        
    def log(self, message: str) -> None:
        """Log message with timestamp."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print(f"[{timestamp}] {message}")
        
    def log_envelope(self, action: str, handler: str, envelope: Dict[str, Any]) -> None:
        """Log envelope details in verbose mode."""
        if self.verbose:
            # Format envelope for readability, converting bytes to hex
            def serialize_envelope(obj: Any) -> Any:
                if isinstance(obj, bytes):
                    return f"<bytes:{len(obj)}:{obj[:20].hex()}...>" if len(obj) > 20 else obj.hex()
                elif isinstance(obj, dict):
                    return {k: serialize_envelope(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [serialize_envelope(v) for v in obj]
                return obj
                
            serializable = serialize_envelope(envelope)
            envelope_str = json.dumps(serializable, indent=2)
            # Truncate large fields
            if len(envelope_str) > 500:
                envelope_str = envelope_str[:500] + "..."
            self.log(f"{action} by {handler}:\n{envelope_str}")
            
    def run(self, protocol_dir: str, input_envelopes: Optional[List[dict[str, Any]]] = None, commands: Optional[List[Dict[str, Any]]] = None, db: Optional[sqlite3.Connection] = None) -> Dict[str, str]:
        """Run the pipeline with given protocol and optional input envelopes or commands.

        Commands should be a list of dicts with 'name' and 'params' keys.
        Returns mapping of event_type -> event_id for events that were stored (one per type).
        """
        self.log(f"Starting pipeline runner")
        self.log(f"Database: {self.db_path}")
        self.log(f"Protocol: {protocol_dir}")

        # Initialize database if not provided
        close_db = False
        if db is None:
            db = get_connection(self.db_path)
            close_db = True
        init_database(db, protocol_dir)

        # Load protocol handlers
        self._load_protocol_handlers(protocol_dir)

        # Track stored events for return value
        stored_events = {}

        # Process commands if provided
        if commands:
            self.log(f"Executing {len(commands)} commands")
            command_envelopes = []
            for i, cmd in enumerate(commands):
                cmd_name = cmd.get('name')
                cmd_params = cmd.get('params', {})
                request_id = f"cmd_{i}"  # Unique ID for this command request

                try:
                    if cmd_name is not None:
                        envelopes = command_registry.execute(cmd_name, cmd_params, db)
                    else:
                        envelopes = []

                    # Add request_id to all envelopes from this command
                    for envelope in envelopes:
                        envelope['request_id'] = request_id

                    command_envelopes.extend(envelopes)
                    self.log(f"Command '{cmd_name}' emitted {len(envelopes)} envelopes")
                except Exception as e:
                    self.log(f"Error executing command '{cmd_name}': {e}")

            if command_envelopes:
                stored = self._process_envelopes(command_envelopes, db)
                stored_events.update(stored)

        # Process input envelopes if provided
        if input_envelopes:
            self.log(f"Processing {len(input_envelopes)} input envelopes")
            stored = self._process_envelopes(input_envelopes, db)
            stored_events.update(stored)

        # Check for any envelopes in outgoing_queue
        # self._process_outgoing_queue(db)  # Disabled - not part of current design

        # Summary
        elapsed = time.time() - self.start_time
        self.log(f"Pipeline complete in {elapsed:.2f}s")
        self.log(f"Envelopes processed: {self.processed_count}")
        self.log(f"Envelopes emitted: {self.emitted_count}")

        if close_db:
            db.close()

        return stored_events
        
    def _load_protocol_handlers(self, protocol_dir: str) -> None:
        """Dynamically load all handlers from a protocol."""
        import importlib
        import os
        
        protocol_name = Path(protocol_dir).name
        self.log(f"Loading handlers for protocol: {protocol_name}")
        
        # Load commands if available
        try:
            commands_module = importlib.import_module(f"protocols.{protocol_name}.commands")
            if hasattr(commands_module, 'register_commands'):
                commands_module.register_commands()
                self.log(f"Loaded commands from protocols.{protocol_name}.commands")
        except ImportError:
            pass
        except Exception as e:
            self.log(f"Failed to load commands: {e}")
        
        handlers_dir = Path(protocol_dir) / "handlers"
        if not handlers_dir.exists():
            self.log(f"No handlers directory found in {protocol_dir}")
            return
            
        # Import handler modules - supports both subdirectory and flat structure
        for item in handlers_dir.iterdir():
            if item.name.startswith("_"):
                continue
                
            # Check for subdirectory structure (old format)
            if item.is_dir():
                handler_file = item / "handler.py"
                if handler_file.exists():
                    module_name = f"protocols.{protocol_name}.handlers.{item.name}.handler"
                    self._load_handler_module(module_name, item.name)
                    
            # Skip *_handler.py wrapper files - we're loading directly from main files now
            elif item.is_file() and item.name.endswith('_handler.py'):
                continue  # Skip wrapper files

            # Load regular .py handler files (excluding __init__ and test files)
            elif item.is_file() and item.name.endswith('.py') and item.name != '__init__.py' and not item.name.startswith('test_'):
                handler_name = item.stem
                module_name = f"protocols.{protocol_name}.handlers.{handler_name}"
                self.log(f"Checking module: {module_name}")
                self._load_handler_module(module_name, handler_name)
                
    def _load_handler_module(self, module_name: str, handler_name: str) -> None:
        """Load a handler module and register handler classes."""
        try:
            module = importlib.import_module(module_name)
            # Look for handler classes
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (hasattr(attr, '__bases__') and 
                    any('Handler' in str(base) for base in attr.__bases__)):
                    handler_instance = attr()
                    registry.register(handler_instance)
                    self.log(f"Registered handler: {handler_instance.name}")
        except Exception as e:
            self.log(f"Failed to load handler {handler_name}: {e}")
                
    def _process_envelopes(self, envelopes: List[dict[str, Any]], db: sqlite3.Connection) -> Dict[str, str]:
        """Process a batch of envelopes through the pipeline.

        Returns mapping of event_type -> event_id for events that were stored (one per type).
        """
        # Convert hex strings to bytes if needed
        processed_envelopes = []
        for env in envelopes:
            env_copy = env.copy()
            if 'raw_data' in env_copy and isinstance(env_copy['raw_data'], str):
                try:
                    env_copy['raw_data'] = bytes.fromhex(env_copy['raw_data'])
                except ValueError:
                    self.log(f"Warning: Invalid hex in raw_data, keeping as string")
            processed_envelopes.append(env_copy)

        # Track all envelopes we process (for tracking stored events)
        all_processed = []

        # Track generated event IDs for placeholder resolution
        generated_ids: Dict[str, List[str]] = {}  # event_type -> [event_ids]

        # Separate events with placeholders from those without
        def has_placeholders(envelope: dict) -> bool:
            """Check if envelope has any @generated: placeholders."""
            def check_value(value: Any) -> bool:
                if isinstance(value, str) and value.startswith('@generated:'):
                    return True
                elif isinstance(value, dict):
                    return any(check_value(v) for v in value.values())
                elif isinstance(value, list):
                    return any(check_value(item) for item in value)
                return False

            if 'event_plaintext' in envelope and check_value(envelope['event_plaintext']):
                return True
            if 'deps' in envelope and check_value(envelope['deps']):
                return True
            return False

        # Process events without placeholders first
        no_placeholder_queue = [env for env in processed_envelopes if not has_placeholders(env)]
        placeholder_queue = [env for env in processed_envelopes if has_placeholders(env)]

        queue = no_placeholder_queue
        iterations = 0
        max_iterations = 1000  # Sanity check to prevent infinite loops

        # Track total envelopes processed across all iterations for diagnostics
        total_envelopes_processed = 0

        while queue and iterations < max_iterations:
            iterations += 1
            total_envelopes_processed += len(queue)

            if self.verbose:
                self.log(f"--- Iteration {iterations} with {len(queue)} envelopes (no placeholders) ---")

            # Warn if we're processing a lot of iterations
            if iterations % 100 == 0:
                self.log(f"WARNING: Pipeline at iteration {iterations}, total envelopes processed: {total_envelopes_processed}")

            next_queue = []
            for envelope in queue:
                self.processed_count += 1

                # Process through all matching handlers
                # The handlers modify the envelope in-place
                emitted = registry.process_envelope(envelope, db)

                # Track generated event_id for placeholder resolution
                if 'event_id' in envelope:
                    event_type = envelope.get('event_type', '')
                    if event_type:
                        if event_type not in generated_ids:
                            generated_ids[event_type] = []
                        generated_ids[event_type].append(envelope['event_id'])

                # Track the processed envelope (handlers may have modified it)
                all_processed.append(envelope)

                if self.verbose and emitted:
                    for handler in registry._handlers:
                        if handler.filter(envelope):
                            self.log_envelope("CONSUMED", handler.name, envelope)
                            for e in emitted:
                                self.log_envelope("EMITTED", handler.name, e)

                # Add emitted envelopes to next queue
                next_queue.extend(emitted)
                self.emitted_count += len(emitted)

            queue = next_queue

        # Now process events with placeholders
        if placeholder_queue:
            if self.verbose:
                self.log(f"--- Processing {len(placeholder_queue)} envelopes with placeholders ---")

            queue = placeholder_queue
            placeholder_iterations = 0

            while queue and placeholder_iterations < max_iterations:
                placeholder_iterations += 1
                total_envelopes_processed += len(queue)

                if self.verbose:
                    self.log(f"--- Placeholder iteration {placeholder_iterations} with {len(queue)} envelopes ---")

                # Warn if we're processing a lot of iterations
                if (iterations + placeholder_iterations) % 100 == 0:
                    self.log(f"WARNING: Pipeline at iteration {iterations + placeholder_iterations}, total envelopes processed: {total_envelopes_processed}")

                next_queue = []
                for envelope in queue:
                    # Resolve placeholders in this envelope before processing
                    self._resolve_placeholders(envelope, generated_ids)

                    self.processed_count += 1

                    # Process through all matching handlers
                    emitted = registry.process_envelope(envelope, db)

                    # Track generated event_id for placeholder resolution
                    if 'event_id' in envelope:
                        event_type = envelope.get('event_type', '')
                        if event_type:
                            if event_type not in generated_ids:
                                generated_ids[event_type] = []
                            generated_ids[event_type].append(envelope['event_id'])

                    # Track the processed envelope
                    all_processed.append(envelope)

                    if self.verbose and emitted:
                        for handler in registry._handlers:
                            if handler.filter(envelope):
                                self.log_envelope("CONSUMED", handler.name, envelope)
                                for e in emitted:
                                    self.log_envelope("EMITTED", handler.name, e)

                    # Add emitted envelopes to next queue
                    next_queue.extend(emitted)
                    self.emitted_count += len(emitted)

                queue = next_queue
                iterations += 1

        if iterations >= max_iterations:
            self.log(f"ERROR: Stopped after {max_iterations} iterations (infinite loop detected)")
            self.log(f"Total envelopes processed: {total_envelopes_processed}")
            raise RuntimeError(f"Pipeline infinite loop detected after {max_iterations} iterations")

        # Track stored events (only return one per type)
        # Use a dict to track unique events by event_id to avoid counting duplicates
        stored_events_by_id = {}

        for envelope in all_processed:
            # Check if this envelope was stored and has a request_id
            if envelope.get('stored') and 'request_id' in envelope:
                event_type = envelope.get('event_type')
                event_id = envelope.get('event_id')

                if event_type and event_id:
                    # Track by event_id to avoid duplicates
                    stored_events_by_id[event_id] = event_type

        # Count unique events per type
        event_counts: Dict[str, int] = {}
        event_ids: Dict[str, str] = {}
        for event_id, event_type in stored_events_by_id.items():
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
            # Store first ID for each type
            if event_type not in event_ids:
                event_ids[event_type] = event_id

        # Only return IDs for types with exactly one event
        stored_ids = {}
        for event_type, count in event_counts.items():
            if count == 1:
                stored_ids[event_type] = event_ids[event_type]

        return stored_ids

    def _resolve_placeholders(self, envelope: dict[str, Any], generated_ids: Dict[str, List[str]]) -> None:
        """Resolve @generated: placeholders in envelope.

        Placeholders have format: @generated:type:index
        e.g., @generated:peer:0 means the first peer event's ID
        """
        def resolve_value(value: Any) -> Any:
            """Recursively resolve placeholders in a value."""
            if isinstance(value, str) and value.startswith('@generated:'):
                # Parse placeholder: @generated:type:index
                parts = value.split(':')
                if len(parts) == 3:
                    _, event_type, index_str = parts
                    try:
                        index = int(index_str)
                        if event_type in generated_ids and index < len(generated_ids[event_type]):
                            resolved = generated_ids[event_type][index]
                            if self.verbose:
                                self.log(f"Resolved placeholder {value} -> {resolved}")
                            return resolved
                    except ValueError:
                        pass
                # If we can't resolve, keep the placeholder
                if self.verbose:
                    self.log(f"Could not resolve placeholder: {value}")
                return value
            elif isinstance(value, dict):
                return {k: resolve_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [resolve_value(item) for item in value]
            else:
                return value

        # Resolve placeholders in event_plaintext
        if 'event_plaintext' in envelope:
            envelope['event_plaintext'] = resolve_value(envelope['event_plaintext'])

        # Resolve placeholders in deps
        if 'deps' in envelope:
            resolved_deps = []
            for dep in envelope['deps']:
                if isinstance(dep, str) and dep.startswith('@generated:'):
                    # Format as proper dependency: type:id
                    parts = dep.split(':')
                    if len(parts) == 3:
                        _, event_type, index_str = parts
                        try:
                            index = int(index_str)
                            if event_type in generated_ids and index < len(generated_ids[event_type]):
                                resolved_id = generated_ids[event_type][index]
                                resolved_dep = f"{event_type}:{resolved_id}"
                                resolved_deps.append(resolved_dep)
                                if self.verbose:
                                    self.log(f"Resolved dependency {dep} -> {resolved_dep}")
                            else:
                                resolved_deps.append(dep)  # Keep placeholder if can't resolve
                        except ValueError:
                            resolved_deps.append(dep)
                    else:
                        resolved_deps.append(dep)
                else:
                    resolved_deps.append(dep)
            envelope['deps'] = resolved_deps

    def _process_outgoing_queue(self, db: sqlite3.Connection) -> None:
        """Process any envelopes in the outgoing queue."""
        cursor = db.execute("""
            SELECT id, envelope_data 
            FROM outgoing_queue 
            WHERE due_ms <= ?
            ORDER BY due_ms
            LIMIT 1000
        """, (int(time.time() * 1000),))
        
        rows = cursor.fetchall()
        if rows:
            self.log(f"Processing {len(rows)} envelopes from outgoing queue")
            
            envelopes = []
            ids_to_delete = []
            
            for row in rows:
                try:
                    envelope = json.loads(row['envelope_data'])
                    envelopes.append(envelope)
                    ids_to_delete.append(row['id'])
                except json.JSONDecodeError:
                    self.log(f"Failed to parse envelope {row['id']} from queue")
                    
            # Process the envelopes
            if envelopes:
                self._process_envelopes(envelopes, db)
                
            # Delete processed envelopes from queue
            if ids_to_delete:
                placeholders = ','.join('?' * len(ids_to_delete))
                db.execute(f"DELETE FROM outgoing_queue WHERE id IN ({placeholders})", ids_to_delete)
                db.commit()
                
    def dump_database(self) -> None:
        """Dump all tables from the database."""
        from .queries import dump_database as dump_db_query
        import json

        self.log(f"\n=== DATABASE DUMP: {self.db_path} ===")

        db = get_connection(self.db_path)

        try:
            # Use the query function to get all table data
            from .db import get_readonly_connection
            readonly_db = get_readonly_connection(db)
            result = dump_db_query(readonly_db, {})

            # Just dump as pretty JSON
            print(json.dumps(result, indent=2, sort_keys=True))
        finally:
            db.close()
            print("\n=== END DATABASE DUMP ===")