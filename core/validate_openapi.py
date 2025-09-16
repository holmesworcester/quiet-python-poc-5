#!/usr/bin/env python3
"""
Validate that a protocol's OpenAPI spec matches discovered operations.

Usage:
  python -m core.validate_openapi --protocol protocols/quiet

Notes:
- This script is protocol-agnostic and lives in core.
- It discovers operations by scanning @command and @query decorated functions.
- It expects the spec at <protocol_dir>/openapi.yaml
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, Set, cast

import yaml


def load_openapi_spec(spec_path: Path) -> Dict[Any, Any]:
    with open(spec_path, 'r') as f:
        return cast(Dict[Any, Any], yaml.safe_load(f))


def extract_operation_ids(spec: Dict[str, Any]) -> Set[str]:
    operation_ids: Set[str] = set()
    for _path, methods in spec.get('paths', {}).items():
        for _method, operation in methods.items():
            if isinstance(operation, dict) and 'operationId' in operation:
                operation_ids.add(operation['operationId'])
    return operation_ids


def discover_code_operations(protocol_dir: Path) -> Set[str]:
    """Discover operation IDs from protocol code.

    - Commands: protocols.<name>.events.<event_type>.commands (functions with _is_command)
    - Queries:  protocols.<name>.events.<event_type>.queries (functions with _is_query)
    - Core ops: core.identity_* (exposed as core.identity_*)
    - System ops: system.dump_database, system.logs
    """
    import importlib.util
    import inspect

    # Ensure repository root on path for dynamic imports
    repo_root = protocol_dir.parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    operation_ids: Set[str] = set()

    # Events (commands + queries)
    events_dir = protocol_dir / 'events'
    if events_dir.exists():
        for event_dir in events_dir.iterdir():
            if not event_dir.is_dir() or event_dir.name.startswith('__'):
                continue
            event_type = event_dir.name

            # commands.py
            commands_file = event_dir / 'commands.py'
            if commands_file.exists():
                spec = importlib.util.spec_from_file_location(f"{event_type}_commands", commands_file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    for name, obj in inspect.getmembers(module):
                        if callable(obj) and hasattr(obj, '_is_command'):
                            operation_ids.add(f"{event_type}.{name}")

            # queries.py
            queries_file = event_dir / 'queries.py'
            if queries_file.exists():
                spec = importlib.util.spec_from_file_location(f"{event_type}_queries", queries_file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    for name, obj in inspect.getmembers(module):
                        if callable(obj) and hasattr(obj, '_is_query'):
                            operation_ids.add(f"{event_type}.{name}")

    # Core identity ops (special-cased)
    core_identity_path = repo_root / 'core' / 'identity.py'
    if core_identity_path.exists():
        spec = importlib.util.spec_from_file_location("core_identity", core_identity_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            for name, obj in inspect.getmembers(module):
                if callable(obj) and name.startswith('core_identity_'):
                    # name is like core_identity_create -> operationId core.identity_create
                    suffix = name.replace('core_identity_', '')
                    operation_ids.add(f"core.identity_{suffix}")

    # System ops (fixed)
    operation_ids.update({'system.dump_database', 'system.logs'})

    return operation_ids


def validate(spec_ops: Set[str], code_ops: Set[str]) -> bool:
    ok = True
    in_spec_not_code = spec_ops - code_ops
    in_code_not_spec = code_ops - spec_ops

    if in_spec_not_code:
        print('❌ Operations in OpenAPI spec but not in code:')
        for op in sorted(in_spec_not_code):
            print(f'  - {op}')
        ok = False

    if in_code_not_spec:
        print('❌ Operations in code but not in OpenAPI spec:')
        for op in sorted(in_code_not_spec):
            print(f'  - {op}')
        ok = False

    if ok:
        print('✅ OpenAPI spec and code are consistent!')
        print(f'   Found {len(spec_ops)} operations')

    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description='Validate protocol OpenAPI consistency')
    parser.add_argument('--protocol', required=True, help='Path to protocol directory (e.g., protocols/quiet)')
    args = parser.parse_args()

    protocol_dir = Path(args.protocol).resolve()
    spec_path = protocol_dir / 'openapi.yaml'
    if not spec_path.exists():
        print(f'❌ OpenAPI spec not found at {spec_path}')
        return 2

    print('🔍 Validating OpenAPI consistency...\n')
    spec = load_openapi_spec(spec_path)
    spec_ops = extract_operation_ids(spec)
    code_ops = discover_code_operations(protocol_dir)

    return 0 if validate(spec_ops, code_ops) else 1


if __name__ == '__main__':
    raise SystemExit(main())

