#!/usr/bin/env python3
"""
Comprehensive fix for all test mechanical issues.
"""
import re
import os
from pathlib import Path

def fix_all_patterns(content):
    """Fix all mechanical patterns in one go."""

    # 1. Fix all command calls - remove , initialized_db or , db
    commands = [
        'create_identity', 'create_network', 'create_user', 'create_transit_secret',
        'create_group', 'create_channel', 'create_message', 'create_key',
        'create_invite', 'create_add', 'join_network', 'create_transit_key'
    ]

    for cmd in commands:
        # Pattern: cmd({...}, initialized_db) -> cmd({...})
        content = re.sub(
            rf'({cmd}\s*\([^)]+)\s*,\s*(initialized_db|db|self\.db)\s*\)',
            r'\1)',
            content
        )

    # 2. Fix command returns - they return single envelope not list
    # Pattern: envelope = create_xxx(...)[0] -> envelope = create_xxx(...)
    content = re.sub(
        r'(\w+)\s*=\s*(create_\w+\([^)]+\))\[0\]',
        r'\1 = \2',
        content
    )

    # Pattern: envelopes = create_xxx(...) -> envelope = create_xxx(...)
    # Then fix references
    content = re.sub(
        r'(\w+)_envelopes\s*=\s*(create_\w+\([^)]+\))',
        r'\1_envelope = \2',
        content
    )
    content = re.sub(
        r'(\w+)_envelopes\[0\]',
        r'\1_envelope',
        content
    )

    # Fix simple envelopes variable
    content = re.sub(
        r'envelopes\s*=\s*(create_\w+\([^)]+\))',
        r'envelope = \1',
        content
    )
    content = re.sub(
        r'envelopes\[0\]',
        r'envelope',
        content
    )

    # 3. Fix query calls - (params, db) -> (db, params)
    queries = [
        'get_users', 'get_user', 'get_user_by_peer_id', 'count_users', 'is_user_in_network',
        'get_messages', 'get_message', 'count_messages', 'list_messages',
        'get_channels', 'get_channel', 'count_channels', 'list_channels',
        'get_groups', 'get_group', 'count_groups', 'list_groups',
        'get_identities', 'get_identity', 'list_identities',
        'list_keys', 'list_transit_keys', 'get_keys', 'get_transit_keys',
        'get', 'list', 'count'
    ]

    for query in queries:
        # Pattern: query({params}, db) -> query(db, {params})
        content = re.sub(
            rf'({query})\s*\(\s*(\{{[^}}]*\}})\s*,\s*(initialized_db|db|self\.db)\s*\)',
            r'\1(\3, \2)',
            content
        )

    # 4. Fix broken for loops from our previous fixes
    # Pattern: for envelope in xxx:\n<no indented block>
    content = re.sub(
        r'for envelope in [^:]+:\s*\n\s*# Process through pipeline if needed',
        '# Process through pipeline if needed',
        content
    )

    # 5. Fix handler class references
    replacements = [
        ('ResolveDepsHandler()', 'resolve_deps_handler, resolve_deps_filter'),
        ('CheckSigHandler()', 'check_sig_handler, check_sig_filter'),
        ('ValidateHandler()', 'ValidateHandler()'),  # This one is still a class
        ('ProjectHandler()', 'ProjectHandler()'),  # This one is still a class
    ]

    for old, new in replacements:
        content = content.replace(f'self.handler = {old}', f'self.handler_func, self.filter_func = {new}')

    # Fix handler method calls
    content = re.sub(r'self\.handler\.filter\(', 'self.filter_func(', content)
    content = re.sub(r'self\.handler\.process\(', 'self.handler_func(', content)

    # 6. Fix assert len(envelopes) == 1 that we broke
    content = re.sub(
        r'assert len\(envelope\) == 1',
        '# Single envelope returned',
        content
    )

    # 7. Fix imports
    content = re.sub(
        r'from protocols\.quiet\.events\.user\.queries import.*list_users.*',
        'from protocols.quiet.events.user.queries import get as get_users, get_user, get_user_by_peer_id, count_users, is_user_in_network',
        content
    )

    content = re.sub(
        r'from protocols\.quiet\.events\.channel\.queries import.*list_channels.*',
        'from protocols.quiet.events.channel.queries import get as get_channels',
        content
    )

    content = re.sub(
        r'from protocols\.quiet\.events\.message\.queries import.*list_messages.*',
        'from protocols.quiet.events.message.queries import get as get_messages',
        content
    )

    content = re.sub(
        r'from protocols\.quiet\.events\.group\.queries import.*list_groups.*',
        'from protocols.quiet.events.group.queries import get as get_groups',
        content
    )

    # Fix list_xxx calls to get_xxx
    content = re.sub(r'\blist_users\b', 'get_users', content)
    content = re.sub(r'\blist_channels\b', 'get_channels', content)
    content = re.sub(r'\blist_messages\b', 'get_messages', content)
    content = re.sub(r'\blist_groups\b', 'get_groups', content)

    return content

def process_file(filepath):
    """Process a single test file."""
    try:
        with open(filepath, 'r') as f:
            content = f.read()

        original = content
        content = fix_all_patterns(content)

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
        'protocols/quiet/tests/handlers',
        'protocols/quiet/tests/scenarios'
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