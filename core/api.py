#!/usr/bin/env python3
"""
HTTP-like API executor for the Quiet protocol.

Maps OpenAPI operationIds to protocol commands and executes them.
Designed for local tooling and tests.
"""

import sys
import os
import json
import yaml
import argparse
import re
import time
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.processor import PipelineRunner, command_registry
from core.database import get_connection


def load_yaml(filepath):
    """Load YAML file."""
    with open(filepath, 'r') as f:
        return yaml.safe_load(f)


def match_path_to_operation(api_spec: Dict, method: str, request_path: str) -> Tuple[str, Dict, Dict]:
    """Return (spec_path, operation, path_params) for a method and path."""
    method = method.lower()
    
    for spec_path, path_item in api_spec.get("paths", {}).items():
        if method not in path_item:
            continue
            
        # Convert OpenAPI path to regex by replacing {param} with named groups
        pattern = spec_path
        param_names = re.findall(r'\{([^}]+)\}', spec_path)
        for param_name in param_names:
            pattern = pattern.replace(f"{{{param_name}}}", f"(?P<{param_name}>[^/]+)")
        
        # Add start and end anchors
        pattern = f"^{pattern}$"
        
        # Try to match
        match = re.match(pattern, request_path)
        if match:
            path_params = match.groupdict()
            return spec_path, path_item[method], path_params
    
    return None, None, None


class APIExecutor:
    """Execute API operations by mapping to commands and queries."""
    
    def __init__(self, protocol_dir: str, db_path: str = "api.db", verbose: bool = False):
        self.protocol_dir = protocol_dir
        self.db_path = db_path
        self.verbose = verbose
        
        # Load OpenAPI spec
        api_path = Path(protocol_dir) / "openapi.yaml"
        if not api_path.exists():
            raise FileNotFoundError(f"No openapi.yaml found in {protocol_dir}")
        self.api_spec = load_yaml(api_path)
        
        # Initialize pipeline runner
        self.runner = PipelineRunner(db_path=db_path, verbose=verbose)
        
        # Initialize database with protocol schema
        db = get_connection(db_path)
        from core.database import init_database
        init_database(db, protocol_dir)
        
        # Load protocol handlers and commands once
        self.runner._load_protocol_handlers(protocol_dir)
        db.close()
        
        # Register protocol commands
        self._register_protocol_commands()
        
        # Keep track of processor logs
        self.processor_logs = []
    
    def _register_protocol_commands(self):
        """Register protocol-specific commands based on OpenAPI spec."""
        protocol_name = Path(self.protocol_dir).name
        
        # Extract all operationIds from the OpenAPI spec
        operation_ids = set()
        for path, path_item in self.api_spec.get("paths", {}).items():
            for method, operation in path_item.items():
                if isinstance(operation, dict) and "operationId" in operation:
                    operation_ids.add(operation["operationId"])
        
        # For each operationId, try to find and register the corresponding command
        for operation_id in operation_ids:
            # Skip query operations (they're handled separately)
            if operation_id.startswith(("list_", "get_", "dump_")):
                continue
                
            # Try to find the command in event type modules
            command_registered = False
            
            # Common mapping of operation patterns to event types
            event_type_mapping = {
                "create_identity": "identity",
                "create_key": "key",
                "create_transit_secret": "transit_secret",
                "create_group": "group",
                "create_channel": "channel",
                "create_message": "message",
                "create_invite": "invite",
                "create_add": "add",
                "create_network": "network",
                "join_network": "user"
            }
            
            if operation_id in event_type_mapping:
                event_type = event_type_mapping[operation_id]
                try:
                    # Import the commands module for this event type
                    module = __import__(
                        f"protocols.{protocol_name}.events.{event_type}.commands",
                        fromlist=[operation_id]
                    )
                    
                    # Look for the command function
                    if hasattr(module, operation_id):
                        command_func = getattr(module, operation_id)
                        command_registry.register(operation_id, command_func)
                        command_registered = True
                        if self.verbose:
                            print(f"Registered command: {operation_id} from {event_type}")
                except ImportError as e:
                    if self.verbose:
                        print(f"Could not import {event_type} commands: {e}")
            
            if not command_registered and self.verbose:
                print(f"Warning: No command found for operationId: {operation_id}")
        
    def execute(self, method: str, path: str, body: Dict[str, Any] = None, 
                query_params: Dict[str, str] = None) -> Tuple[int, Dict[str, Any]]:
        """Execute an API operation and return (status_code, response_body)."""
        
        # Match path to operation
        spec_path, operation, path_params = match_path_to_operation(self.api_spec, method, path)
        if not operation:
            return 404, {"error": f"No operation found for {method} {path}"}
        
        operation_id = operation.get("operationId")
        if not operation_id:
            return 500, {"error": "No operationId defined"}
        
        # Build params combining path params, query params, and body
        params = {}
        if path_params:
            params.update(path_params)
        if query_params:
            params.update(query_params)
        if body:
            params.update(body)
        
        try:
            # Check if this is a command or a query
            if operation_id in command_registry._commands:
                # Execute as command
                result = self._execute_command(operation_id, params)
            else:
                # Execute as query
                result = self._execute_query(operation_id, params)
            
            return 200, result
            
        except ValueError as e:
            return 400, {"error": str(e)}
        except Exception as e:
            return 500, {"error": str(e)}
    
    def _execute_command(self, command_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a command through the pipeline."""
        # Clear logs
        self.processor_logs = []
        
        # Capture logs during execution
        original_log = self.runner.log
        original_log_envelope = self.runner.log_envelope
        
        def capture_log(message: str):
            if message and "]" in message:
                timestamp = message.split("]")[0][1:]
            else:
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            self.processor_logs.append({
                "timestamp": timestamp,
                "message": message or ""
            })
            original_log(message)
        
        def capture_envelope_log(action: str, handler: str, envelope: Dict[str, Any]):
            self.processor_logs.append({
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "action": action,
                "handler": handler,
                "envelope": envelope
            })
            # Don't call original_log_envelope to avoid duplicate output
        
        self.runner.log = capture_log
        self.runner.log_envelope = capture_envelope_log
        
        # Run the command
        commands = [{"name": command_name, "params": params}]
        db = get_connection(self.db_path)
        
        # Reset runner state
        self.runner.processed_count = 0
        self.runner.emitted_count = 0
        
        # Execute commands
        command_envelopes = []
        for cmd in commands:
            envelopes = command_registry.execute(cmd["name"], cmd["params"], db)
            command_envelopes.extend(envelopes)
        
        # Process through pipeline
        if command_envelopes:
            self.runner._process_envelopes(command_envelopes, db)
        
        # Process outgoing queue
        # self.runner._process_outgoing_queue(db)  # Disabled - not part of current design
        
        db.commit()
        db.close()
        
        # Restore original logging
        self.runner.log = original_log
        self.runner.log_envelope = original_log_envelope
        
        # Return command result
        return {
            "success": True,
            "processed_count": self.runner.processed_count,
            "emitted_count": self.runner.emitted_count
        }
    
    def _execute_query(self, query_name: str, params: Dict[str, Any]) -> Any:
        """Execute a query."""
        # Import query functions from protocol
        protocol_name = Path(self.protocol_dir).name
        
        # Special system queries
        if query_name == "dump_database":
            return self._dump_database()
        elif query_name == "get_processor_logs":
            limit = params.get("limit", 100)
            # Convert limit to int if it's a string
            if isinstance(limit, str):
                limit = int(limit)
            return self.processor_logs[-limit:]
        
        # Try to find the query in event types
        protocol_name = Path(self.protocol_dir).name
        
        # Map operation IDs to event types and query modules
        query_mapping = {
            'list_identities': ('identity', 'list'),
            'list_keys': ('key', 'list'),
            'list_transit_keys': ('transit_secret', 'list'),
        }
        
        if query_name in query_mapping:
            event_type, query_module = query_mapping[query_name]
            try:
                module = __import__(
                    f"protocols.{protocol_name}.events.{event_type}.queries.{query_module}", 
                    fromlist=[query_name]
                )
                query_func = getattr(module, query_name)
                
                db = get_connection(self.db_path)
                result = query_func(params, db)
                db.close()
                
                return result
            except (ImportError, AttributeError) as e:
                raise ValueError(f"Query '{query_name}' not found: {e}")
        else:
            raise ValueError(f"Unknown query: {query_name}")
    
    def _dump_database(self) -> Dict[str, List[Dict[str, Any]]]:
        """Dump all tables from the database."""
        db = get_connection(self.db_path)
        cursor = db.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = cursor.fetchall()
        
        result = {}
        for table in tables:
            table_name = table['name']
            if table_name.startswith('sqlite_'):
                continue
            
            # Get all rows
            cursor.execute(f"SELECT * FROM {table_name}")
            rows = cursor.fetchall()
            
            # Convert to list of dicts
            result[table_name] = []
            for row in rows:
                row_dict = {}
                for key in row.keys():
                    value = row[key]
                    # Convert bytes to hex for JSON serialization
                    if isinstance(value, bytes):
                        value = value.hex()
                    row_dict[key] = value
                result[table_name].append(row_dict)
        
        db.close()
        return result


class APIRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the API server."""
    
    def __init__(self, *args, api_executor: APIExecutor = None, **kwargs):
        self.api_executor = api_executor
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET requests."""
        self._handle_request('GET')
    
    def do_POST(self):
        """Handle POST requests."""
        self._handle_request('POST')
    
    def do_PUT(self):
        """Handle PUT requests."""
        self._handle_request('PUT')
    
    def do_DELETE(self):
        """Handle DELETE requests."""
        self._handle_request('DELETE')
    
    def _handle_request(self, method: str):
        """Handle any HTTP request."""
        # Parse URL
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query_params = urllib.parse.parse_qs(parsed.query)
        
        # Flatten query params (take first value for each key)
        query_params = {k: v[0] for k, v in query_params.items()}
        
        # Read body for POST/PUT
        body = None
        if method in ['POST', 'PUT']:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 0:
                body_bytes = self.rfile.read(content_length)
                try:
                    body = json.loads(body_bytes)
                except json.JSONDecodeError:
                    self.send_error(400, "Invalid JSON")
                    return
        
        # Execute operation
        status_code, response_body = self.api_executor.execute(
            method, path, body, query_params
        )
        
        # Send response
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response_body, indent=2).encode())
    
    def log_message(self, format, *args):
        """Override to reduce logging."""
        if self.api_executor.verbose:
            super().log_message(format, *args)


def run_server(protocol_dir: str, port: int = 8080, db_path: str = "api.db", verbose: bool = False):
    """Run the API server."""
    api_executor = APIExecutor(protocol_dir, db_path, verbose)
    
    # Create request handler with api_executor
    def handler(*args, **kwargs):
        APIRequestHandler(*args, api_executor=api_executor, **kwargs)
    
    server = HTTPServer(('localhost', port), handler)
    print(f"API server running on http://localhost:{port}")
    print(f"Protocol: {protocol_dir}")
    print(f"Database: {db_path}")
    print("Press Ctrl+C to stop")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Run API server for a protocol')
    parser.add_argument('protocol', help='Protocol directory (e.g., protocols/quiet)')
    parser.add_argument('--port', type=int, default=8080, help='Port to listen on')
    parser.add_argument('--db', default='api.db', help='Database path')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Validate protocol directory
    protocol_path = Path(args.protocol)
    if not protocol_path.exists():
        print(f"Error: Protocol directory '{args.protocol}' does not exist")
        sys.exit(1)
    
    run_server(args.protocol, args.port, args.db, args.verbose)


if __name__ == '__main__':
    main()