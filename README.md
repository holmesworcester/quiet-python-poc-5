# Quiet Python POC 5

An implementation of the Quiet Protocol - an E2EE, P2P protocol for team chat (Slack alternative) using an event-driven pipeline architecture.

## Architecture

This implementation uses a pure handler/pipeline design where:
- Events flow through handlers in envelopes
- Handlers filter on specific envelope traits and emit new/modified envelopes
- Real SQLite database for persistence
- Real cryptography using PyNaCl

## Project Structure

```
quiet-python-poc-5/
├── core/                    # Framework code
│   ├── envelope.py         # Envelope type for carrying event data
│   ├── handler.py          # Handler base class and registry
│   ├── database.py         # Database setup and utilities
│   └── crypto.py           # Cryptographic utilities (PyNaCl wrapper)
├── protocols/              # Protocol implementations
│   └── quiet/             # The Quiet protocol
│       ├── handlers/      # Pipeline handlers
│       │   ├── receive_from_network.py  # Process raw network data
│       │   ├── decrypt_transit.py       # Decrypt transit layer
│       │   ├── decrypt_event.py         # Decrypt event layer
│       │   ├── resolve_deps.py          # Resolve event dependencies
│       │   ├── check_sig.py             # Verify signatures
│       │   ├── validate.py              # Type-specific validation
│       │   └── project.py               # Apply events to state
│       └── event_types/   # Event type definitions
│           └── identity.py              # Identity event (no dependencies)
└── test_pipeline.py       # Test script demonstrating the pipeline
```

## Pipeline Flow

1. **receive_from_network** - Extracts transit key ID and ciphertext from raw data
2. **decrypt_transit** - Decrypts transit layer using stored keys
3. **decrypt_event** - Extracts event plaintext
4. **resolve_deps** - Ensures all dependencies are available
5. **check_sig** - Verifies event signatures
6. **validate** - Type-specific validation logic
7. **project** - Applies validated events to database state

## Setup

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install pynacl
```

## Running

```bash
# Run the pipeline test
python test_pipeline.py
```

This will:
1. Create a test identity event
2. Encrypt it with transit-layer encryption
3. Simulate receiving it over the network
4. Process it through the entire pipeline
5. Store the validated event in the database

## Implementation Status

### Completed
- ✅ Envelope type and handler registry
- ✅ SQLite database schema
- ✅ Real crypto using PyNaCl
- ✅ Core pipeline handlers
- ✅ Identity event type (bootstrap case)
- ✅ Successful event flow through pipeline

### Next Steps
- Create more event types: key, network, user, message
- Implement creation pipeline for self-generated events
- Add outgoing pipeline handlers
- Build network simulator
- Implement sync mechanism with bloom filters

## Design Decisions

- **No JSON tests** - Direct pipeline testing with real events
- **Real SQL from start** - SQLite with proper schema
- **Real crypto** - PyNaCl for all operations
- **Handler filters** - Each handler declares what envelopes it processes
- **Identity bootstrap** - Identity events have no dependencies