"""
Production pipeline runner for processing envelopes through handlers.
Supports verbose logging and database inspection.
"""
import importlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable

from .db import get_connection, init_database
from .handler import registry
from .types import Envelope


class CommandRegistry:
    """Registry for handler-defined commands."""
    
    def __init__(self):
        self._commands: Dict[str, Callable] = {}
        
    def register(self, name: str, command: Callable):
        """Register a command function."""
        self._commands[name] = command
        
    def execute(self, name: str, params: Dict[str, Any], db: sqlite3.Connection) -> List[Envelope]:
        """Execute a command and return emitted envelope."""
        if name not in self._commands:
            raise ValueError(f"Unknown command: {name}")
            
        command = self._commands[name]
        
        # Check if command uses old signature (with db parameter)
        import inspect
        sig = inspect.signature(command)
        if len(sig.parameters) == 2:
            # Old signature: (params, db) -> List[Envelope]
            result = command(params, db)
            return result if isinstance(result, list) else [result]
        else:
            # New signature: (params) -> Envelope
            result = command(params)
            return [result] if result else []
        
    def list_commands(self) -> List[str]:
        """Return list of registered command names."""
        return sorted(self._commands.keys())


command_registry = CommandRegistry()


class PipelineRunner:
    """Production pipeline runner with configurable logging."""
    
    def __init__(self, db_path: str = "quiet.db", verbose: bool = False):
        self.db_path = db_path
        self.verbose = verbose
        self.processed_count = 0
        self.emitted_count = 0
        self.start_time = time.time()
        
    def log(self, message: str):
        """Log message with timestamp."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print(f"[{timestamp}] {message}")
        
    def log_envelope(self, action: str, handler: str, envelope: Dict[str, Any]):
        """Log envelope details in verbose mode."""
        if self.verbose:
            # Format envelope for readability, converting bytes to hex
            def serialize_envelope(obj):
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
            
    def run(self, protocol_dir: str, input_envelopes: Optional[List[Envelope]] = None, commands: Optional[List[Dict[str, Any]]] = None):
        """Run the pipeline with given protocol and optional input envelopes or commands.
        
        Commands should be a list of dicts with 'name' and 'params' keys.
        """
        self.log(f"Starting pipeline runner")
        self.log(f"Database: {self.db_path}")
        self.log(f"Protocol: {protocol_dir}")
        
        # Initialize database
        db = get_connection(self.db_path)
        init_database(db, protocol_dir)
        
        # Load protocol handlers
        self._load_protocol_handlers(protocol_dir)
        
        # Process commands if provided
        if commands:
            self.log(f"Executing {len(commands)} commands")
            command_envelopes = []
            for cmd in commands:
                cmd_name = cmd.get('name')
                cmd_params = cmd.get('params', {})
                
                try:
                    envelopes = command_registry.execute(cmd_name, cmd_params, db)
                    command_envelopes.extend(envelopes)
                    self.log(f"Command '{cmd_name}' emitted {len(envelopes)} envelopes")
                except Exception as e:
                    self.log(f"Error executing command '{cmd_name}': {e}")
                    
            if command_envelopes:
                self._process_envelopes(command_envelopes, db)
        
        # Process input envelopes if provided
        if input_envelopes:
            self.log(f"Processing {len(input_envelopes)} input envelopes")
            self._process_envelopes(input_envelopes, db)
        
        # Check for any envelopes in outgoing_queue
        # self._process_outgoing_queue(db)  # Disabled - not part of current design
        
        # Summary
        elapsed = time.time() - self.start_time
        self.log(f"Pipeline complete in {elapsed:.2f}s")
        self.log(f"Envelopes processed: {self.processed_count}")
        self.log(f"Envelopes emitted: {self.emitted_count}")
        
        db.close()
        
    def _load_protocol_handlers(self, protocol_dir: str):
        """Dynamically load all handlers from a protocol."""
        import importlib
        import os
        
        protocol_name = Path(protocol_dir).name
        
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
                    
            # Check for flat structure (new format: {name}_handler.py)
            elif item.is_file() and item.name.endswith('_handler.py'):
                handler_name = item.name[:-11]  # Remove _handler.py
                # Import as normal Python module
                module_name = f"protocols.{protocol_name}.handlers.{item.stem}"
                self._load_handler_module(module_name, handler_name)
                
    def _load_handler_module(self, module_name: str, handler_name: str):
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
                
    def _process_envelopes(self, envelopes: List[Envelope], db: sqlite3.Connection):
        """Process a batch of envelopes through the pipeline."""
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
        
        queue = processed_envelopes
        iterations = 0
        max_iterations = 100  # Prevent infinite loops
        
        while queue and iterations < max_iterations:
            iterations += 1
            if self.verbose:
                self.log(f"--- Iteration {iterations} with {len(queue)} envelopes ---")
            
            next_queue = []
            for envelope in queue:
                self.processed_count += 1
                
                # Process through all matching handlers
                emitted = registry.process_envelope(envelope, db)
                
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
            
        if iterations >= max_iterations:
            self.log(f"WARNING: Stopped after {max_iterations} iterations (possible loop)")
            
    def _process_outgoing_queue(self, db: sqlite3.Connection):
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
                
    def dump_database(self):
        """Dump all tables from the database."""
        self.log(f"\n=== DATABASE DUMP: {self.db_path} ===")
        
        db = get_connection(self.db_path)
        cursor = db.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = cursor.fetchall()
        
        for table in tables:
            table_name = table['name']
            if table_name.startswith('sqlite_'):
                continue
                
            print(f"\n--- Table: {table_name} ---")
            
            # Get table info
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            col_names = [col['name'] for col in columns]
            
            # Get row count
            cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
            count = cursor.fetchone()['count']
            print(f"Rows: {count}")
            
            if count > 0 and count <= 100:  # Only show data for small tables
                cursor.execute(f"SELECT * FROM {table_name}")
                rows = cursor.fetchall()
                
                # Pretty print as table
                print("| " + " | ".join(col_names) + " |")
                print("|" + "|".join(["-" * (len(col) + 2) for col in col_names]) + "|")
                
                for row in rows:
                    values = []
                    for i, col in enumerate(col_names):
                        value = row[col]
                        # Truncate long values
                        if isinstance(value, (str, bytes)) and len(str(value)) > 50:
                            value = str(value)[:47] + "..."
                        values.append(str(value))
                    print("| " + " | ".join(values) + " |")
                    
            elif count > 100:
                print(f"(Table too large to display, showing first 5 rows)")
                cursor.execute(f"SELECT * FROM {table_name} LIMIT 5")
                rows = cursor.fetchall()
                
                for i, row in enumerate(rows):
                    print(f"Row {i+1}: {dict(row)}")
                    
        db.close()
        print("\n=== END DATABASE DUMP ===")