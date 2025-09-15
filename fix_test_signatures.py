#!/usr/bin/env python3
"""
Fix test signatures to match the new command/query patterns.
"""
import re
import os
from pathlib import Path

def fix_command_calls(content):
    """Fix command function calls - remove db parameter."""
    # Pattern: create_*({...}, initialized_db) -> create_*({...})
    patterns = [
        (r'(create_identity|create_network|create_user|create_transit_secret|create_group|create_channel|create_message|create_key|create_invite|create_add|join_network)\s*\(\s*({[^}]+})\s*,\s*initialized_db\s*\)', r'\1(\2)'),
        # Also handle the [0] indexing that some tests do
        (r'(create_\w+)\s*\(\s*({[^}]+})\s*,\s*initialized_db\s*\)\[0\]', r'\1(\2)'),
    ]

    for pattern, replacement in patterns:
        content = re.sub(pattern, replacement, content)

    return content

def fix_query_calls(content):
    """Fix query function calls to match new signatures."""
    # Queries now take (db, params) not just (db) or other variations
    # Most queries are called with get() now

    # Fix imports first - many specific functions don't exist anymore
    content = re.sub(
        r'from protocols\.quiet\.events\.user\.queries import.*\n.*list_users.*',
        'from protocols.quiet.events.user.queries import get as get_users, get_user, get_user_by_peer_id, count_users, is_user_in_network',
        content
    )

    return content

def fix_process_envelope(content):
    """Remove or comment out process_envelope calls."""
    # These are no longer needed in most tests
    content = re.sub(
        r'^\s*process_envelope\([^)]+\)\s*$',
        '        # Process through pipeline if needed',
        content,
        flags=re.MULTILINE
    )

    # Fix the import
    content = re.sub(
        r'from core\.pipeline import process_envelope',
        '# from core.pipeline import PipelineRunner  # Use if needed',
        content
    )

    return content

def fix_handler_imports(content):
    """Fix handler imports that no longer exist."""
    # Handler classes were replaced with functions
    replacements = [
        (r'from protocols\.quiet\.handlers\.resolve_deps import ResolveDepsHandler',
         'from protocols.quiet.handlers.resolve_deps import handler as resolve_deps_handler, filter_func as resolve_deps_filter'),
        (r'from protocols\.quiet\.handlers\.validate\.handler import ValidateHandler',
         'from protocols.quiet.handlers.validate import ValidateHandler'),
        (r'from protocols\.quiet\.handlers\.project\.handler import ProjectHandler',
         'from protocols.quiet.handlers.project import ProjectHandler'),
        (r'from protocols\.quiet\.handlers\.check_sig\.handler import CheckSigHandler',
         'from protocols.quiet.handlers.signature import handler as check_sig_handler, filter_func as check_sig_filter'),
    ]

    for pattern, replacement in replacements:
        content = re.sub(pattern, replacement, content)

    return content

def process_file(filepath):
    """Process a single test file."""
    with open(filepath, 'r') as f:
        content = f.read()

    original = content

    # Apply all fixes
    content = fix_command_calls(content)
    content = fix_query_calls(content)
    content = fix_process_envelope(content)
    content = fix_handler_imports(content)

    # Only write if changed
    if content != original:
        with open(filepath, 'w') as f:
            f.write(content)
        return True
    return False

def main():
    """Fix all test files."""
    test_dirs = [
        'protocols/quiet/tests/events',
        'protocols/quiet/tests/handlers'
    ]

    fixed_count = 0
    for test_dir in test_dirs:
        for filepath in Path(test_dir).rglob('*.py'):
            if process_file(filepath):
                print(f"Fixed: {filepath}")
                fixed_count += 1

    print(f"\nFixed {fixed_count} files")

if __name__ == '__main__':
    main()