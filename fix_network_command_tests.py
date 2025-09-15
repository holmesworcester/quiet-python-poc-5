#!/usr/bin/env python3
"""
Fix tests that call create_network to handle the fact it returns two envelopes.
"""
import re
from pathlib import Path

def fix_file(filepath, content):
    """Fix create_network calls in a file."""

    # Pattern 1: Single envelope assignment
    content = re.sub(
        r'(\s+)network_envelope = create_network\(',
        r'\1network_envelope, identity_envelope = create_network(',
        content
    )

    # Pattern 2: network1_envelope
    content = re.sub(
        r'(\s+)network1_envelope = create_network\(',
        r'\1network1_envelope, identity1_envelope = create_network(',
        content
    )

    # Pattern 3: network2_envelope
    content = re.sub(
        r'(\s+)network2_envelope = create_network\(',
        r'\1network2_envelope, identity2_envelope = create_network(',
        content
    )

    # Pattern 4: envelopes1 (already plural but needs tuple)
    content = re.sub(
        r'(\s+)envelopes1 = create_network\(',
        r'\1network_envelope1, identity_envelope1 = create_network(',
        content
    )

    # Pattern 5: envelopes2
    content = re.sub(
        r'(\s+)envelopes2 = create_network\(',
        r'\1network_envelope2, identity_envelope2 = create_network(',
        content
    )

    # Fix references to envelopes1[0] and envelopes2[0]
    content = re.sub(r'envelopes1\[0\]', 'network_envelope1', content)
    content = re.sub(r'envelopes2\[0\]', 'network_envelope2', content)

    return content

def main():
    """Fix all test files."""
    test_files = [
        'tests/events/user/test_query.py',
        'tests/events/network/test_command.py',
        'tests/events/channel/test_command.py',
        'tests/events/channel/test_query.py',
        'tests/events/group/test_query.py',
        'tests/events/message/test_query.py',
    ]

    for file_path in test_files:
        filepath = Path(file_path)
        if not filepath.exists():
            continue

        try:
            with open(filepath, 'r') as f:
                content = f.read()

            original = content
            content = fix_file(filepath, content)

            if content != original:
                with open(filepath, 'w') as f:
                    f.write(content)
                print(f"Fixed: {filepath}")
        except Exception as e:
            print(f"Error processing {filepath}: {e}")

if __name__ == '__main__':
    main()