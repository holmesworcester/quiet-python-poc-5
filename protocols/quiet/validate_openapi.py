#!/usr/bin/env python3
"""
Validate that OpenAPI spec matches actual command implementations.

This ensures operation IDs in openapi.yaml match the registered commands.
Run this as part of CI/CD or pre-commit to ensure consistency.
"""
import sys
import yaml
from pathlib import Path
from typing import Dict, Set, List, Any, cast

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from core.commands import CommandRegistry


def load_openapi_spec(spec_path: Path) -> Dict[Any, Any]:
    """Load and parse the OpenAPI specification."""
    with open(spec_path, 'r') as f:
        return cast(Dict[Any, Any], yaml.safe_load(f))


def extract_operation_ids(spec: Dict) -> Set[str]:
    """Extract all operation IDs from OpenAPI spec."""
    operation_ids = set()

    # Walk through all paths and methods
    for path, methods in spec.get('paths', {}).items():
        for method, operation in methods.items():
            if isinstance(operation, dict) and 'operationId' in operation:
                operation_ids.add(operation['operationId'])

    return operation_ids


def get_registered_commands(protocol_dir: Path) -> Set[str]:
    """Get all registered command operation IDs by scanning for @command decorated functions."""
    import importlib.util
    import inspect

    operation_ids = set()

    # Load all commands from the protocol events
    events_dir = protocol_dir / 'events'
    for event_dir in events_dir.iterdir():
        if event_dir.is_dir() and not event_dir.name.startswith('__'):
            event_type = event_dir.name
            commands_file = event_dir / 'commands.py'

            if commands_file.exists():
                # Load the module
                spec = importlib.util.spec_from_file_location(f"{event_type}_commands", commands_file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    # Find all @command decorated functions
                    for name, obj in inspect.getmembers(module):
                        if callable(obj) and hasattr(obj, '_is_command'):
                            # Use simple consistent naming: event_type.function_name
                            operation_id = f'{event_type}.{name}'
                            operation_ids.add(operation_id)

            # Also check for query files
            queries_file = event_dir / 'queries.py'
            if queries_file.exists():
                spec = importlib.util.spec_from_file_location(f"{event_type}_queries", queries_file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    # Find all @query decorated functions
                    for name, obj in inspect.getmembers(module):
                        if callable(obj) and hasattr(obj, '_is_query'):
                            # Use simple consistent naming: event_type.function_name
                            operation_id = f'{event_type}.{name}'
                            operation_ids.add(operation_id)

    # Also check for core commands (they use a different pattern)
    core_module_path = project_root / 'core' / 'identity.py'
    if core_module_path.exists():
        spec = importlib.util.spec_from_file_location("core_identity", core_module_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Core functions follow the pattern core_identity_X
            for name, obj in inspect.getmembers(module):
                if callable(obj) and name.startswith('core_identity_'):
                    # Convert core_identity_create -> core.identity_create
                    operation_name = name.replace('core_identity_', '')
                    operation_id = f'core.identity_{operation_name}'
                    operation_ids.add(operation_id)

    # Add hardcoded system operations (these don't follow the standard pattern)
    system_operations = [
        'system.dump_database',
        'system.logs'
    ]
    operation_ids.update(system_operations)

    return operation_ids


def validate_consistency(spec_ops: Set[str], code_ops: Set[str]) -> bool:
    """Validate that OpenAPI spec and code are consistent."""
    # Find mismatches
    in_spec_not_code = spec_ops - code_ops
    in_code_not_spec = code_ops - spec_ops

    success = True

    if in_spec_not_code:
        print("❌ Operations in OpenAPI spec but not in code:")
        for op in sorted(in_spec_not_code):
            print(f"  - {op}")
        success = False

    if in_code_not_spec:
        print("❌ Operations in code but not in OpenAPI spec:")
        for op in sorted(in_code_not_spec):
            print(f"  - {op}")
        success = False

    if success:
        print("✅ OpenAPI spec and code are consistent!")
        print(f"   Found {len(spec_ops)} operations")

    return success


def suggest_openapi_paths(missing_ops: Set[str]) -> None:
    """Suggest OpenAPI path definitions for missing operations."""
    if not missing_ops:
        return

    print("\n📝 Suggested OpenAPI definitions for missing operations:\n")

    for op in sorted(missing_ops):
        event_type, func_name = op.split('.', 1)

        # Guess reasonable path and method
        if 'create' in func_name or 'join' in func_name:
            method = 'post'
        elif 'get' in func_name or 'list' in func_name:
            method = 'get'
        else:
            method = 'post'

        # Generate path
        path = f"/{event_type}"
        if 'get' in func_name or 'list' in func_name:
            path += "s"  # Pluralize for queries

        print(f"""  {path}:
    {method}:
      operationId: {op}
      summary: {func_name.replace('_', ' ').title()}
      tags:
        - {event_type}
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                type: object
""")


def main() -> None:
    """Main validation function."""
    protocol_dir = Path(__file__).parent
    spec_path = protocol_dir / 'openapi.yaml'

    if not spec_path.exists():
        print(f"❌ OpenAPI spec not found at {spec_path}")
        sys.exit(1)

    print("🔍 Validating OpenAPI consistency...\n")

    # Load OpenAPI spec
    spec = load_openapi_spec(spec_path)
    spec_ops = extract_operation_ids(spec)

    # Get registered commands
    code_ops = get_registered_commands(protocol_dir)

    # Validate consistency
    if not validate_consistency(spec_ops, code_ops):
        # Suggest fixes
        in_code_not_spec = code_ops - spec_ops
        suggest_openapi_paths(in_code_not_spec)
        sys.exit(1)


if __name__ == '__main__':
    main()
