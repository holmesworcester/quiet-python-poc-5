#!/usr/bin/env python3
"""
Fix all validator tests to use envelope instead of separate event and metadata.
"""
import re
from pathlib import Path

# Find all validator test files
test_files = list(Path("protocols/quiet/tests/events").glob("*/test_validator.py"))

for test_file in test_files:
    print(f"Processing {test_file}...")
    
    with open(test_file, 'r') as f:
        content = f.read()
    
    # Pattern 1: validate(event, envelope_metadata)
    # Replace with validate(envelope) where envelope contains the event
    content = re.sub(
        r'envelope_metadata = \{"event_type": "(\w+)"\}\s*\n\s*assert validate\((\w+), envelope_metadata\)',
        r'envelope = {"event_plaintext": \2, "event_type": "\1"}\n        assert validate(envelope)',
        content
    )
    
    # Pattern 2: validate(sample_XXX_event, envelope_metadata)
    content = re.sub(
        r'envelope_metadata = \{"event_type": "(\w+)"\}\s*\n\s*assert validate\((sample_\w+_event), envelope_metadata\)',
        r'envelope = {"event_plaintext": \2, "event_type": "\1"}\n        assert validate(envelope)',
        content
    )
    
    # Pattern 3: event = sample_XXX_event.copy() followed by validate
    content = re.sub(
        r'(event = sample_\w+_event\.copy\(\).*?\n(?:.*?\n)*?)\s*envelope_metadata = \{"event_type": "(\w+)"\}\s*\n\s*assert validate\(event, envelope_metadata\)',
        r'\1        envelope = {"event_plaintext": event, "event_type": "\2"}\n        assert validate(envelope)',
        content,
        flags=re.DOTALL
    )
    
    # Pattern 4: with pytest.raises followed by validate call
    content = re.sub(
        r'envelope_metadata = \{"event_type": "(\w+)"\}\s*\n\s*validate\((\w+), envelope_metadata\)',
        r'envelope = {"event_plaintext": \2, "event_type": "\1"}\n        validate(envelope)',
        content
    )
    
    # Write back
    with open(test_file, 'w') as f:
        f.write(content)
    
    print(f"  Fixed {test_file}")

print("Done!")