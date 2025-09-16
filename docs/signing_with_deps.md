# Signing with Dependencies - Clean Architecture

## Key Insight
Use the dependency resolution system for both signing and verification!

## How It Works

### For Signature Verification (incoming events)
1. Event arrives with a `peer_id` field
2. `resolve_deps` fetches the peer event → gets public key
3. `signature` handler uses the public key from resolved deps to verify

### For Signing (outgoing events)
1. Self-created event includes its own `peer_id` as a dependency
2. `resolve_deps` fetches the peer event → gets public key
3. `signature` handler:
   - Gets public key from resolved deps
   - Uses `sign_with_identity(public_key, data)` to sign
   - Core identity function matches by public key to find private key

## Benefits
- **No special cases** - signing and verification use same flow
- **Clean separation** - handlers don't need database access for identity
- **Consistent** - all events work the same way
- **Pure handlers** - signature handler only needs resolved deps

## Implementation

### Signature Handler
```python
def sign_event(envelope):
    # Get peer_id from the event
    peer_id = envelope['event_plaintext'].get('peer_id')

    # Get peer data from resolved deps
    peer_dep = envelope['resolved_deps'].get(f'peer:{peer_id}')
    public_key = peer_dep['event_plaintext']['public_key']

    # Sign using core identity (finds private key by public key)
    from core.identity import sign_with_identity
    signature = sign_with_identity(public_key, canonical_data)

    envelope['event_plaintext']['signature'] = signature
    return envelope
```

### Message Creation
```python
def create_message(params):
    # Message includes peer_id of its author
    event = {
        'type': 'message',
        'peer_id': peer_id,  # The peer creating this message
        'content': content,
        ...
    }

    # Include peer as dependency so signature handler can sign
    envelope = {
        'event_plaintext': event,
        'deps': [
            f'peer:{peer_id}',  # Our own peer for signing
            f'channel:{channel_id}'  # Channel for context
        ]
    }
```

## Core Identity Changes

Add a function that can find identity by public key:
```python
def sign_with_identity(public_key_hex: str, data: bytes) -> str:
    """Sign data using the identity with this public key."""
    # Find identity by public key
    identity = get_identity_by_public_key(public_key_hex)
    if not identity:
        raise ValueError(f"No identity with public key {public_key_hex}")
    return identity.sign(data).hex()
```

## Clean Architecture Result
- Commands create events with `peer_id` and include peer as dependency
- Resolve deps fetches all dependencies including the peer
- Signature handler uses resolved peer's public key for signing/verification
- No database access needed in signature handler
- No special cases between self-created and received events