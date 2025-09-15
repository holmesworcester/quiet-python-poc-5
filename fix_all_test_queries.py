#!/usr/bin/env python3
"""
Fix all query function calls to use (db, params) signature.
"""
import re
import os
from pathlib import Path

def fix_query_signatures(content):
    """Fix query function signatures to (db, params) order."""

    # Common query functions that need fixing
    query_funcs = [
        'get_users', 'get_user', 'get_user_by_peer_id', 'count_users', 'is_user_in_network',
        'get_messages', 'get_message', 'count_messages',
        'get_channels', 'get_channel', 'count_channels',
        'get_groups', 'get_group', 'count_groups',
        'get_identities', 'get_identity',
        'list_keys', 'list_transit_keys',
        'get', 'list', 'count'  # Generic names
    ]

    for func in query_funcs:
        # Pattern: func({params}, db) -> func(db, {params})
        pattern = rf'({func})\s*\(\s*(\{{[^}}]*\}})\s*,\s*(initialized_db|db|self\.db)\s*\)'
        replacement = r'\1(\3, \2)'
        content = re.sub(pattern, replacement, content)

        # Also fix cases where params is a variable
        pattern = rf'({func})\s*\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*,\s*(initialized_db|db|self\.db)\s*\)'
        # Check if it looks like a dict variable (not a db variable)
        def replacer(match):
            if match.group(2) not in ['initialized_db', 'db', 'self']:
                return f'{match.group(1)}({match.group(3)}, {match.group(2)})'
            return match.group(0)
        content = re.sub(pattern, replacer, content)

    return content

def fix_command_returns(content):
    """Fix expectations that commands return lists."""
    # Commands now return single envelopes, not lists

    # Fix patterns like: envelope = create_xxx(...)[0]
    content = re.sub(
        r'(\w+_envelope\s*=\s*create_\w+\([^)]+\))\[0\]',
        r'\1',
        content
    )

    # Fix patterns like: envelopes = create_xxx(...) followed by envelopes[0]
    content = re.sub(
        r'(\w+)_envelopes\s*=\s*(create_\w+\([^)]+\))',
        r'\1_envelope = \2',
        content
    )

    # Then fix references to xxx_envelopes[0] -> xxx_envelope
    content = re.sub(
        r'(\w+)_envelopes\[0\]',
        r'\1_envelope',
        content
    )

    return content

def process_file(filepath):
    """Process a single test file."""
    try:
        with open(filepath, 'r') as f:
            content = f.read()

        original = content

        # Apply fixes
        content = fix_query_signatures(content)
        content = fix_command_returns(content)

        # Only write if changed
        if content != original:
            with open(filepath, 'w') as f:
                f.write(content)
            return True
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
    return False

def main():
    """Fix all test files."""
    test_dirs = [
        'protocols/quiet/tests/events',
        'protocols/quiet/tests/handlers'
    ]

    fixed_count = 0
    for test_dir in test_dirs:
        for filepath in Path(test_dir).rglob('test_*.py'):
            if process_file(filepath):
                print(f"Fixed: {filepath}")
                fixed_count += 1

    print(f"\nFixed {fixed_count} files")

if __name__ == '__main__':
    main()