# Using Key Dependencies for Encryption

## Current Conclusions

### Outgoing Encryption
For outgoing encryption, we can eliminate dedicated transit tables entirely:
- Commands declare encryption keys as dependencies: `deps: ["key:<key_id>"]` or `deps: ["peer:<peer_id>"]`
- Commands choose which transit key to use (not handlers)
- resolve_deps fetches the encryption material (group keys, peer public keys)
- Crypto handlers read from `envelope['resolved_deps']` - no database access needed

### Incoming Decryption
Incoming decryption can also use the dependency system:
- Keys are persistently stored as key events or peer/identity events in the event store
- For sync-request events, include `identity_id` (not `peer_id`) as the key reference since identity events contain the private key
- The key_id in raw data tells us which key to use for decryption (or unsealing) 

## Pros of Dependency-Based Encryption

### Simplicity
- **Unified key resolution**: All key material flows through the same dependency system
- **No special tables**: Eliminates transit_secret tables and special handling
- **Pure handlers**: Crypto handlers become pure transformations without DB access
- **Clear data flow**: Envelopes declare what they need, pipeline provides it

### Security Benefits
- **Ephemeral transit keys**: Outgoing transit keys can be single-use for perfect forward secrecy
- **Explicit dependencies**: Clear audit trail of what keys are used where
- **No key reuse**: Each message can have unique transit encryption

### Architectural Cleanliness
- **Single source of truth**: Dependencies system handles all resource resolution
- **Testability**: Handlers can be tested with mocked resolved_deps
- **Protocol agnostic**: Core doesn't need to know about transit_secret specifics

## Cons and Challenges

### Incoming Message Handling
- **Key discovery problem**: How do we know which key decrypts an incoming message?
  - **Solution**: key_id or identity_id is included in the raw message data
- **Storage requirement**: Need persistent storage for decryption keys
  - **Solution**: Store as events in the event store like everything else
- **Gossip compatibility**: Must handle messages encrypted with various keys
  - **Solution**: Gossip using keys you think peers know (e.g., recently used keys from sync-requests)

### Performance Considerations
- **Dependency resolution overhead**: Every outgoing message needs dep resolution
- **Storage growth**: Transit keys needed for forward secrecy anyway, but they're short-lived

### Implementation Complexity
- **Key rotation**: How do we handle old keys for late-arriving messages?
  - **Solution**: Grace period between key end-of-life and deletion (ttl)

## Proposed Architecture

### Outgoing Flow
```
1. Command creates envelope with:
   - deps: ["identity:<identity_id>"] for transit wrapping (until ephemeral keys exist)
   - deps: ["key:<key_id>"] for event encryption (group keys)
2. resolve_deps provides the needed keys
3. event_crypto encrypts using key from resolved deps
4. transit_crypto wraps using identity from resolved deps
5. Raw message sent includes transit_key_id (identity_id)
```

### Incoming Flow
```
1. Message arrives with transit_key_id (identity_id) in raw data
2. resolve_deps looks up identity_id → finds our private key
3. transit_crypto decrypts to reveal event_ciphertext
4. event_crypto decrypts using revealed key_ref
5. Message processed normally
```

### Key Storage Strategy

All keys are stored as events in the event store:
- **Identity events**: Contain private keys for our identities
- **Peer events**: Contain public keys for other peers
- **Key events**: Contain group encryption keys
- **No transit_secret table needed**: Use existing event types

The dependency system resolves these events when needed for encryption/decryption.

## Key Insights

1. **Commands control key selection**: Commands decide which keys to use, not handlers
2. **Two types of encryption dependencies**:
   - `identity_id` for transit wrapping (temporary until ephemeral keys)
   - `key_id` for event encryption (group keys)
3. **Everything is an event**: No special transit_secret tables - use existing event types
4. **Dependency resolution handles everything**: Both outgoing and incoming use the same dependency system

## Implementation Path

1. **Remove transit_secret event type**: No longer needed
2. **Update sync-request commands**: Use identity_id as the transit key reference
3. **Modify resolve_deps**: Handle identity/peer/key lookups for transit encryption
4. **Simplify handlers**: Remove database access from crypto handlers
5. **Grace period for key deletion**: Implement ttl for handling late messages

## Benefits of This Approach

- **Unified architecture**: Everything flows through events and dependencies
- **No special cases**: Transit encryption uses the same patterns as event encryption
- **Forward secrecy built-in**: Short-lived transit keys are natural with this model
- **Gossip-ready**: Can decrypt any message where we have the key
- **Simple mental model**: "If you have the key event, you can decrypt"