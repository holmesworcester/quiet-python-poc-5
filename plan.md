# Envelope-centric design with Handlers and Filter-based Subscriptions

My previous handlers-only approach ran into severe friction in these areas:

1. Blocking events with missing dependencies and unblocking when they arrived
2. Using a SQL database and switching between a SQL database and an in-memory dict
3. Handling real crypto operations and testing them

I'm anticipating even more friction once I start thinking about transit-layer encryption where there are multiple steps that events go through. So much functionality will be crammed into the sync-request handler and the process_incoming job for adding and removing transit-layer and event-layer encryption. 

I'm curious if the following design will be simpler:

1. An eventbus that anything can emit() to
2. Envelopes that carry event-related data.
3. Handlers that subscribe to envelopes (emitted to the eventbus) with certain traits based on a filter.

### Rules

- No protocol-specific fields in `/core`: protocols define everything.
- No dict or in-memory persistence for anything: all data is stored in SQL, compatible with their being 10M envelopes.
- Self-QA the runner by running it in CLI and reading output (later we will hook this up to a demo.py TUI app)
- The only envelope id is event_id (blake2b-16 hash of the complete signed event plaintext in its canonical 512-byte form). This matches ideal_protocol_design.md where events are 512 bytes and id(evt) = crypto_generichash(16, evt).  
- No protocol event types should read or write the db ever. Projectors just emit deltas and framework handles it. Everything in event types is a pure function.
- Commands are pure functions that emit envelopes with dependency declarations, not with resolved data
- Handlers are pure functions that transform envelopes without database access

### Database Access Rules

1. **Event Type Functions (Commands, Validators, Projectors) - NO Database Access**
   - Must be pure functions without any database operations
   - Commands: `(params: dict[str, Any]) -> Envelope`
   - Validators: `(envelope: Envelope) -> bool`
   - Projectors: `(envelope: Envelope) -> list[Delta]`
   - Decorators enforce this with runtime checks for database access patterns

2. **Handlers - Read/Write Database Access**
   - Only handlers can modify the database
   - Access database through the `db: sqlite3.Connection` parameter
   - Examples: resolve_deps reads events, project handler applies deltas

3. **Queries - Read-Only Database Access**
   - Use `@query` decorator which provides `ReadOnlyConnection`
   - Cannot execute INSERT, UPDATE, DELETE, CREATE, DROP, ALTER operations
   - First parameter must be `db: ReadOnlyConnection`
   - Used by API endpoints and application logic to read projected state

4. **Enforcement Mechanisms**
   - `@command`, `@validator`, `@projector` decorators check source code for DB access
   - `ReadOnlyConnection` wrapper prevents write operations in queries
   - Runtime errors if event functions attempt database access
   - Type system enforces correct signatures 

# Envelope Structure and Dependencies

## Envelope Fields
An envelope is a container for event data and metadata used by the pipeline. Key fields include:

- `event_plaintext`: The actual event data (before encryption)
- `event_ciphertext`: The encrypted event data  
- `event_type`: Type of the event (e.g., "message", "identity", "group")
- `event_id`: Blake2b hash of event ciphertext
- `self_created`: Boolean indicating if this was created locally
- `peer_id`: The identity that created/signed the event
- `network_id`: Which network this event belongs to
- `deps`: Array of dependency references (e.g., `["identity:abc123", "key:xyz789"]`)
- `resolved_deps`: Object containing fetched dependency data
- `local_metadata`: Local-only data (never sent over network)
- Pipeline state flags: `deps_included_and_valid`, `sig_checked`, `validated`, etc.

## Dependency Resolution

Commands declare dependencies they need in the `deps` array:
```python
envelope = {
    "event_plaintext": {"type": "message", "content": "Hello"},
    "event_type": "message",
    "self_created": True,
    "peer_id": "identity_abc123",
    "deps": ["identity:identity_abc123"]  # Need identity for signing
}
```

The `resolve_deps` handler:
1. Reads the `deps` array
2. For each dependency:
   - Fetches validated events from the database
   - For identity dependencies, ALSO includes local_metadata (private keys) from a separate local storage
   - For transit/key dependencies, may include local secrets that were never events
3. Adds them to `resolved_deps`:
```python
envelope["resolved_deps"] = {
    "identity:identity_abc123": {
        "event_plaintext": {"type": "identity", "peer_id": "..."},  # From validated events
        "local_metadata": {"private_key": "..."}  # From local secret storage, NOT an event
    },
    "transit_key:xyz789": {
        "transit_secret": "...",  # Local secret, never was an event
        "network_id": "..."
    }
}
```

Note: Local secrets (private keys, transit secrets) are stored separately and are NEVER events that go through validation. They are only included in resolved_deps for local use and are stripped before any network transmission.

## Local Metadata

`local_metadata` is envelope data that:
- Contains sensitive local information (e.g., private keys)
- Is never sent over the network
- Is included when resolving dependencies for local operations
- Is stored locally but never sent over the network (enforced by type system)

# Type Definitions

## Dependency Types

```typescript
// Base validated event
interface ValidatedEvent {
  event_plaintext: object
  event_type: string
  event_id: string
  validated: true
}

// Identity with optional local private key
interface IdentityDep extends ValidatedEvent {
  event_type: "identity"
  local_metadata?: { private_key: bytes }
}

// Transit key (local secret, not an event)
interface TransitKeyDep {
  transit_secret: bytes
  network_id: string
}

// Address for routing
interface AddressDep {
  ip: string
  port: number
  public_key?: string
}

// Union of all dependency types
type ResolvedDep = ValidatedEvent | IdentityDep | TransitKeyDep | AddressDep

// Key reference with explicit type discrimination
interface PeerKeyRef {
  kind: "peer"
  id: string  // peer_id for KEM-sealed to identity/prekey
}

interface GroupKeyRef {
  kind: "key"
  id: string  // key event_id for symmetric encryption
}

type KeyRef = PeerKeyRef | GroupKeyRef

// Strict type for outgoing network data
interface OutgoingTransitEnvelope {
  transit_ciphertext: bytes
  transit_key_id: string
  dest_ip: string
  dest_port: number
  due_ms?: number
  // No other fields allowed - enforces no leaks
}
```

# Pipelines

Handlers use filters to subscribe to the eventbus. We use these to create pipelines. Each handler transforms envelopes by adding, modifying, or removing fields.

## Incoming Pipeline: Network → Validated Storage

Note: an alternate version of this would let framework store and return events, fetch valid deps, and block/unblock deps.

### 1. receive_from_network
- **Input Type:**
  ```typescript
  interface NetworkData {
    origin_ip: string
    origin_port: number
    received_at: number
    raw_data: bytes
  }
  ```
- **Output Type:**
  ```typescript
  interface TransitEnvelope {
    transit_key_id: string
    transit_ciphertext: bytes
    origin_ip: string
    origin_port: number
    received_at: number  // Preserve timestamp!
    deps: string[]  // Added: ["transit_key:{transit_key_id}"]
  }
  ```
- **Filter:** Has `origin_ip`, `origin_port`, `received_at`, `raw_data`
- **Transform:** Parses raw_data to extract transit encryption fields, preserves metadata, adds deps array

### 2. resolve_deps (First Pass)
- **Input Type:**
  ```typescript
  interface NeedsDepsEnvelope {
    deps?: string[]
    deps_included_and_valid?: boolean | false
    unblocked?: boolean
    [key: string]: any
  }
  ```
- **Output Type:**
  ```typescript
  interface ResolvedDepsEnvelope {
    deps_included_and_valid: true
    resolved_deps: Record<string, ResolvedDep>
    [key: string]: any
  } | {
    missing_deps: true
    missing_dep_list: string[]
    [key: string]: any
  }
  ```
- **Filter:** `deps` exists AND (`deps_included_and_valid` is false OR `unblocked: true`)
- **Note:** Only resolves from already-validated events. Keeps resolved_deps in envelope for reuse.

### 3. transit_crypto_handler
- **Input Type:**
  ```typescript
  interface TransitEncryptedEnvelope {
    deps_included_and_valid: true
    transit_key_id: string
    transit_ciphertext: bytes
    resolved_deps: Record<string, ResolvedDep>
    [key: string]: any
  }
  ```
- **Output Type:**
  ```typescript
  interface EventEncryptedEnvelope {
    network_id: string
    key_ref: KeyRef  // Discriminated union: peer vs key
    event_ciphertext: bytes
    event_id: string  // blake2b-16 hash of canonical signed plaintext
    write_to_store: true
    [key: string]: any
  }
  ```
- **Filter:** `deps_included_and_valid: true` AND has `transit_key_id` AND `transit_ciphertext` AND NOT `key_ref`
- **Transform:** Uses transit key from resolved_deps to decrypt
- **Emits:** Second envelope with `write_to_store: true`

### 4. remove (Early Check - Optional)
- **Input Type:**
  ```typescript
  interface EventWithId {
    event_id: string
    should_remove?: boolean
    [key: string]: any
  }
  ```
- **Output Type:** Same envelope with `should_remove: false` OR drops envelope
- **Filter:** Has `event_id` AND `should_remove` is not false
- **Note:** Early removal based only on event_id (e.g., explicit deletion records)

### 5. event_crypto_handler
- **Input Type:**
  ```typescript
  interface EncryptedEvent {
    deps_included_and_valid: true
    should_remove: false
    key_ref: KeyRef  // Discriminated union: peer vs key
    event_ciphertext?: bytes
    resolved_deps: Record<string, ResolvedDep>
    [key: string]: any
  }
  ```
- **Output Type (Key Event):**
  ```typescript
  interface UnsealedKeyEvent {
    event_type: "key"
    key_id: string
    unsealed_secret: bytes
    group_id: string
    prekey_id: string     // Which prekey was used
    tag_id: string        // KEM tag for decapsulation
    write_to_store: true
    sig_checked: true     // Bypass signature verification
    validated: true       // Self-validating after unsealing
    [key: string]: any
  }
  ```
- **Output Type (Regular Event):**
  ```typescript
  interface DecryptedEvent {
    event_plaintext: object
    event_type: string
    write_to_store: true
    [key: string]: any
  }
  ```
- **Filter:** 
  - Decrypt: `deps_included_and_valid: true` AND `should_remove: false` AND `key_ref` exists AND no `event_plaintext`
  - Encrypt: `validated: true` AND has `event_plaintext` AND no `event_ciphertext`
- **Transform:**
  - If `key_ref.kind == "peer"`: Unseal using KEM with identity/prekey
  - If `key_ref.kind == "key"`: Decrypt using symmetric key from resolved key event
- **Note:** Combined handler for encryption, decryption, and key unsealing

### 6. event_store
- **Input Type:**
  ```typescript
  interface StorableEvent {
    write_to_store: true
    event_id?: string
    event_ciphertext?: bytes
    event_plaintext?: object
    key_id?: string
    received_at?: number  // Preserved from network receipt
    origin_ip?: string
    origin_port?: number
    [key: string]: any
  }
  ```
- **Output Type:** Same with `stored: true`
- **Filter:** `write_to_store: true`
- **Action:** Stores event data in database, including network metadata for observability
- **Purge Function:**
  - Called by validate handler when event fails validation
  - Marks event as `purged: true` in store but keeps event_id for duplicate rejection
  - Sets TTL for eventual cleanup of purged events
  - Prevents invalid events from being processed while maintaining blocking for duplicates

### 7. remove (Content-Based - Optional)
- **Input Type:**
  ```typescript
  interface DecryptedEventWithType {
    event_id: string
    event_plaintext: object
    event_type: string
    should_remove?: boolean
    [key: string]: any
  }
  ```
- **Output Type:** Same envelope with `should_remove: false` OR drops envelope
- **Filter:** Has `event_plaintext` AND `event_type` AND `should_remove` is not false
- **Action:** Calls event-type-specific Removers with full event data
- **Note:** Can now make informed decisions (e.g., remove messages when channel is deleted)

### 8. resolve_deps (Second Pass for Signature)
- **Input/Output Types:** Same as first pass
- **Filter:** `event_plaintext` exists AND `sig_checked` is not true AND (`deps_included_and_valid` is false OR needs peer resolution)
- **Note:** Resolves peer_id from plaintext to get public key for signature verification

### 9. signature_handler
- **Input Type:**
  ```typescript
  interface SignableOrVerifiableEvent {
    event_plaintext: object & { signature?: bytes, peer_id?: string }
    sig_checked?: boolean
    self_created?: boolean
    deps_included_and_valid: true
    resolved_deps: Record<string, ResolvedDep>
    event_type?: string  // Skip if "key"
    [key: string]: any
  }
  ```
- **Output Type:** Same with `sig_checked: true` and `event_id: string` or `error: string`
- **Filter:** 
  - Skip: `event_type: "key"` (key events are sealed, not signed)
  - Sign: `self_created: true` AND `deps_included_and_valid: true` AND no signature
  - Verify: `event_plaintext` exists AND `sig_checked` is not true AND `deps_included_and_valid: true`
- **Transform:**
  - Signs/verifies signature
  - Generates `event_id` as blake2b-16 hash of canonical signed plaintext (512 bytes)
- **Note:** Combined handler for both signing and verification

### 10. membership_check (If Applicable)
- **Input Type:**
  ```typescript
  interface GroupEvent {
    event_plaintext: object & { group_id?: string, group_member_id?: string, user_id?: string }
    is_group_member?: boolean
    [key: string]: any
  }
  ```
- **Output Type:** Same with `is_group_member: true`
- **Filter:** event_plaintext has `group_id` AND `is_group_member` is false/absent
- **Validates:** group_member_id matches user_id and group_id

### 11. validate
- **Input Type:**
  ```typescript
  interface ValidatableEvent {
    event_plaintext: object
    event_type: string
    sig_checked: true
    is_group_member?: true
    resolved_deps?: Record<string, ValidatedEvent>
    event_id: string  // Required for purging
    [key: string]: any
  }
  ```
- **Output Type:** Same with `validated: true` or `error: string`
- **Filter:** Has `event_plaintext`, `event_type`, `sig_checked: true`, AND (no `group_id` in plaintext OR `is_group_member: true`)
- **Action:** 
  - Calls event type specific validator with full envelope
  - If validation fails: calls event_store.purge(event_id) to mark as invalid
  - Purged events remain in store for duplicate detection but won't be processed

### 12. resolve_deps (Combined with Unblock Logic)
- **Note:** This handler now combines dependency resolution AND unblocking logic
- **Input Type:**
  ```typescript
  interface NeedsDepsOrValidatedEvent {
    // For resolution
    deps?: string[]
    deps_included_and_valid?: boolean
    unblocked?: boolean
    
    // For unblocking
    validated?: true
    missing_deps?: true
    event_id?: string
    missing_deps_list?: string[]
    retry_count?: number
    [key: string]: any
  }
  ```
- **Output:** 
  - Resolution: Same envelope with `resolved_deps` OR drops if missing deps
  - Unblocking: Emits previously blocked events with `unblocked: true`
- **Filter:** 
  - Resolution: Has `deps` AND (`deps_included_and_valid` is false OR `unblocked` is true)
  - Unblocking: `validated: true` OR `missing_deps: true`
- **Action:** 
  - Resolves dependencies from validated events and local secrets
  - Blocks events with missing dependencies
  - Unblocks events when ALL dependencies are satisfied
  - Tracks retry count (max 100) to prevent infinite loops
  - Manages blocked_events and blocked_event_deps tables

### 13. project (Per Event Type)
- **Input Type:**
  ```typescript
  interface ProjectableEvent {
    validated: true
    event_type: string
    event_plaintext: object
    [key: string]: any
  }
  ```
- **Output Type:**
  ```typescript
  interface ProjectedEvent extends ProjectableEvent {
    projected: true
    deltas: Delta[]
  }
  ```
- **Filter:** `validated: true` AND matching event_type
- **Action:** Calls event type specific projector

## Creation Pipeline: Command → Storage

### Phase 1: Creation and Validation

### 1. Command (e.g., create_message)
- **Input Type:**
  ```typescript
  interface MessageParams {
    content: string
    channel_id: string
    identity_id: string  // Which identity to use for signing
  }
  ```
- **Output Type:**
  ```typescript
  interface CommandEnvelope {
    event_plaintext: {
      type: "message"
      content: string
      channel_id: string
      peer_id: string  // Included in event data
    }
    event_type: "message"
    self_created: true
    deps: string[]  // ["identity:identity_abc123"]
  }
  ```
- **Note:** peer_id is included in event_plaintext as it's part of the event data

### 2. resolve_deps
- **Input/Output Types:** Same as incoming pipeline
- **Note:** Resolves identity with private key in local_metadata. Keeps resolved_deps in envelope for reuse by subsequent handlers.

### 3. signature_handler
- **Input Type:**
  ```typescript
  interface SignableEnvelope {
    event_plaintext: object & { peer_id: string }
    self_created: true
    deps_included_and_valid: true
    resolved_deps: Record<string, ResolvedDep>
    [key: string]: any
  }
  ```
- **Output Type:**
  ```typescript
  interface SignedEnvelope extends SignableEnvelope {
    event_plaintext: object & { signature: bytes }
    event_id: string  // Generated from canonical signed plaintext
  }
  ```
- **Filter:** `self_created: true` AND `deps_included_and_valid: true` AND no signature
- **Transform:** 
  - Uses private key from resolved_deps["identity:..."] to sign
  - Generates `event_id` as blake2b-16 hash of canonical signed plaintext (512 bytes)
- **Note:** Same handler used for both signing and verification

### 4-10. Validation Flow
- Same handlers as incoming: signature_handler → membership_check → validate

### Phase 2: Storage (After Validation)

### 11. event_crypto_handler
- **Input Type:**
  ```typescript
  interface ValidatedPlaintext {
    validated: true
    event_plaintext: object
    event_ciphertext?: undefined
    [key: string]: any
  }
  ```
- **Output Type:**
  ```typescript
  interface EncryptedEvent {
    event_ciphertext: bytes
    key_ref: KeyRef  // Which key was used for encryption
    event_id: string  // blake2b-16 hash of canonical signed plaintext
    write_to_store: true
    [key: string]: any
  }
  ```
- **Filter:** `validated: true` AND has `event_plaintext` AND no `event_ciphertext`
- **Transform:** Encrypts plaintext (event_id already set by signature_handler)
- **Note:** Same handler used for encryption, decryption, and key unsealing

### 12. event_store
- Same as incoming pipeline

### 13. project
- Same as incoming pipeline

## Outgoing Pipeline: Storage → Network

### 1. Outgoing Command (e.g., send_sync_request)
- **Input Type:**
  ```typescript
  interface SendParams {
    event_id: string      // Event to send
    peer_id: string       // Destination peer
    due_ms?: number       // When to send (optional)
  }
  ```
- **Output Type:**
  ```typescript
  interface OutgoingEnvelope {
    outgoing: true
    deps: string[]  // Dependencies to resolve
    deps_included_and_valid: false
  }
  ```
- **Transform:** Creates envelope with deps for event, address, keys, etc.

### 2. resolve_deps
- **Input/Output Types:** Same as incoming pipeline
- **Transform:** Resolves all outgoing dependencies:
  - `address:address_id` → dest_ip, dest_port
  - `event:event_id` → event_plaintext, event_ciphertext
  - `transit_key:transit_key_id` → transit_secret
  - `peer:peer_id`, `user:user_id` → peer/user data

### 3. check_outgoing
- **Input Type:**
  ```typescript
  interface OutgoingWithDeps {
    outgoing: true
    deps_included_and_valid: true
    resolved_deps: Record<string, ResolvedDep>
    event_type?: string
    outgoing_checked?: undefined
    [key: string]: any
  }
  ```
- **Output Type:** Same with `outgoing_checked: true`
- **Filter:** `outgoing: true` AND `deps_included_and_valid: true` AND no `outgoing_checked`
- **Validates:** 
  - address, peer, and user all match and are consistent
  - event_type is not a secret type (identity_secret, transit_secret, etc.)

### 4. event_crypto_handler (If Needed)
- **Input/Output Types:** Same as creation pipeline
- **Filter:** `outgoing_checked: true` AND no `event_ciphertext`
- **For:** Newly created events being gossiped

### 5. transit_crypto_handler
- **Input Type:**
  ```typescript
  interface OutgoingEncrypted {
    outgoing_checked: true
    event_ciphertext: bytes
    transit_key_id: string
    resolved_deps: Record<string, ResolvedDep>  // Contains transit_secret
    [key: string]: any
  }
  ```
- **Output Type:** `OutgoingTransitEnvelope` (exact type required by send_to_network)
- **Filter:** `outgoing_checked: true` AND has `event_ciphertext` AND `transit_key_id`
- **Transform:** Encrypts with transit key, removes all plaintext/secrets

### 6. send_to_network
- **Input Type:**
  ```typescript
  interface OutgoingTransitEnvelope {
    transit_ciphertext: bytes
    transit_key_id: string
    dest_ip: string
    dest_port: number
    due_ms?: number
    // That's it! No other fields allowed
  }
  ```
- **Filter:** Has all required transit fields (enforced by type system)
- **Action:** Sends to network using framework's send() function
- **Note:** Type system ensures no secrets or metadata can leak. strip_for_send is no longer needed!

## Key Design Principles

1. **deps_included_and_valid** resets to false when any handler adds new dependencies or resolve_deps scans for missing in its filter!
2. **write_to_store: true** triggers storage at multiple points in the pipeline
3. **Handlers are pure functions** that only transform envelopes
4. **Event IDs** are blake2b hashes of ciphertext, not plaintext
5. **Transit encryption** wraps event encryption for forward secrecy
6. **Local metadata** (like private keys) stays local and is never sent

## Network Simulator

- **Filter:** `stripped_for_send: true`
- **Action:** Simulates network latency and routes back to receive_from_network
- **Note:** Requires network design that can differentiate incoming data and route to proper networks/identities

# Event Types

Each event type is a self-contained module with these components:

## Folder Structure

```
protocols/quiet/
├── __init__.py
├── commands.py           # Command registry and loader
├── openapi.yaml         # API specification
├── handlers/            # Pipeline handlers
│   ├── __init__.py
│   ├── check_sig.handler.py
│   ├── decrypt_event.handler.py
│   ├── decrypt_event.schema.sql    # Handler's SQL tables
│   ├── project.handler.py
│   ├── resolve_deps.handler.py
│   └── validate.handler.py
├── events/              # Event type modules  
│   ├── message/
│   │   ├── __init__.py
│   │   ├── commands.py      # create_message() function
│   │   ├── projector.py     # project() function
│   │   ├── queries.py       # get_messages() etc.
│   │   ├── validator.py     # validate() function
│   │   ├── remover.py      # should_remove() function
│   │   └── message.schema.sql
│   ├── identity/
│   │   ├── __init__.py
│   │   ├── commands.py
│   │   ├── projector.py
│   │   ├── queries.py
│   │   ├── validator.py
│   │   └── identity.schema.sql
│   └── (other event types...)
└── tests/
    ├── handlers/
    │   └── test_*.py
    └── events/
        ├── message/
        │   ├── test_commands.py
        │   ├── test_projector.py
        │   └── test_validator.py
        └── (mirror event structure)
```

## Components

1. **Command** (creator): Pure function that takes params and returns envelopes
   - Input: User parameters (e.g., `{"message": "Hello", "channel_id": "123"}`)
   - Output: Envelope with unsigned event and dependency declarations
   - Never accesses database or performs crypto operations
   - Declares dependencies needed for signing/encryption in `deps` array

2. **Validator**: Pure function that validates event structure
   - Input: Full envelope data and all (and only!) valid deps complete `deps` array (validators often need depency events)
   - Output: Boolean (valid/invalid)
   - Checks required fields, formats, and business rules
   - Does not check signatures and typically does not check group membership (handled by pipeline)

3. **Projector**: Pure function that converts events to database deltas
   - Input: Validated envelope
   - Output: Array of delta operations
   - Deltas specify database operations: `{"op": "insert", "table": "messages", "data": {...}}`
   - Never executes database operations directly

4. **Schema**: SQL table definitions for this event type
   - Located in `schema.sql` in the event type folder
   - Defines tables that projector deltas will populate
   - Example: messages table, message_reactions table, etc.

5. **Query** (reader): Functions that read projected state
   - Input: Query parameters
   - Output: Requested data
   - Directly queries SQL tables defined in schema.sql
   - Used by API endpoints and application logic

6. **Remover**: Pure function for cascading deletions
   - Input: Event ID and deletion context
   - Output: Boolean (should remove this event)
   - Determines if an event should be removed based on other removals
   - Example: Remove messages when their channel is removed

# API and Commands

## API Design

The API exposes high-level operations that map to commands:
- POST `/messages` → `create_message` command
- POST `/groups` → `create_group` command  
- POST `/invites` → `create_invite` command
- POST `/users/join` → `join_network` command

API requests include:
- User intent parameters (e.g., message content, channel ID)
- Identity context (which identity is performing the action)
- Never include private keys or low-level crypto details

## Command Interface

Commands accept parameters that mirror API requests:
```python
# API-friendly parameters
params = {
    "content": "Hello world",
    "channel_id": "channel_123", 
    "identity_id": "identity_abc"  # Which identity is sending
}

# Command creates envelope with dependencies (pure function, no DB access!)
envelope = create_message(params)
# Returns: {
#     "event_plaintext": {"type": "message", "content": "Hello world", ...},
#     "event_type": "message",
#     "peer_id": "identity_abc",
#     "deps": ["identity:identity_abc"]  # Declares need for identity's key
# }
```

The framework:
1. Routes API calls to appropriate commands
2. Runs handlers in sequence via the event bus
3. Provides crypto functions (sign, decrypt, etc.) to handlers
4. Provides apply() function that executes deltas on the SQL database

Handlers in the pipeline:
- `resolve_deps` handler fetches dependencies (including identity with private key)
- `sign` handler signs events using resolved identity from resolved_deps
- Other handlers perform validation, encryption, storage, etc. 

# Crypto

The framework provides crypto functions hash, kdf, encrypt, decrypt, sign, check_sig, seal, unseal that all handlers and event type commands, projectors, etc. can use. 

# Data

Handlers define and maintain their own SQLite tables and indexes which can be used by other handlers (e.g. validator maintains a table (id, isValid) which other handlers like resolve_deps can use.)

We have a protocol-defined event_store handler that stores `event_id`, `ciphertext`, `key_id`, `plaintext` for all events and emits envelopes with `stored:True` 

# Testing

## Pure Function Testing (No Database Access)

### Event Type Components:
- **Command**: Given params, verify correct envelope structure and deps array
  - Test envelope contains correct event_type, event data, and dependency declarations
  - No signature verification (signing happens in pipeline)
  - Example: `create_message({"content": "Hi", "channel_id": "123"})` returns envelope with `deps: ["identity:abc123"]`

- **Validator**: Test acceptance/rejection of event structures
  - Valid events return True
  - Invalid events (missing fields, wrong types) return False
  - No database lookups or external validation

- **Projector**: Given envelope, verify correct delta operations
  - Test delta structure: `{"op": "insert", "table": "messages", "data": {...}}`
  - Multiple deltas for complex projections
  - Pure transformation of event to database operations

- **Remover**: Given removal context, verify cascade logic
  - Returns True for events that should be removed
  - Example: `should_remove(message_id, {"removed_channels": ["chan123"]})` returns True

### Handlers:
- **Filter Test**: Verify handler processes correct envelopes
  - Handler ignores envelopes missing required fields
  - Handler processes envelopes matching its filter

- **Transformation Test**: Verify correct envelope transformation
  - Input envelope + resolved_deps → output envelope
  - Example: sign handler with identity in resolved_deps adds signature to event

## Integration Testing (With Database)

- **Query**: Test with real SQLite database
  - Apply deltas to fresh database
  - Verify query results match expected
  - Test complex queries with joins

- **End-to-end**: Full pipeline execution
  - Command → resolve_deps → sign → validate → project
  - Verify final database state 

Testing infra-specific handlers:

- **send_to_network:** must provide correct params to send(params) function for a given envelope

Testing infra

- **apply(deltas):** given a db state and deltas, the final state is correct (use db seeder and db snapshots so that states can be expressed, compared as json)
- **receive(raw_network_data):** given some unit of raw network data from an ip and port, creates envelopes with `origin_ip`, `origin_port`, `received_at`, and `raw_data`
- **crypto:** basic functional tests of all crypto functions

# Type Safety

## Design Goals
- Flexible envelope type that can carry any event data through the pipeline
- Strict type checking for handler functions and event-specific operations
- Runtime validation at handler boundaries

## Implementation

### Envelope Types
- Base `Envelope` remains a flexible `TypedDict(total=False)` allowing any fields
- Specialized envelope types document required fields at each pipeline stage:
  - `NetworkEnvelope`: Raw network data (`origin_ip`, `origin_port`, `raw_data`)
  - `TransitEnvelope`: Transit encrypted (`transit_key_id`, `transit_ciphertext`)
  - `DecryptedEnvelope`: Decrypted event (`event_plaintext`, `event_type`, `peer_id`)
  - `ValidatedEnvelope`: Validated event (`sig_checked: True`, `validated: True`)

### Handler Typing
- All handlers accept and return base `Envelope` type for flexibility
- Runtime validation using `validate_envelope_fields()` at handler entry points
- Type guards in filter functions narrow envelope types
- Cast functions provide safe runtime type conversion with validation

### Event-Specific Types
- Event data types defined as `TypedDict` classes (e.g., `MessageEventData`, `IdentityEventData`)
- Registry maps event types to their data structures
- Commands use typed parameter classes (e.g., `MessageParams`)
- Validators/projectors use generic protocols with event-specific type parameters

### Function Signatures
- `CommandFunc`: `(params: dict[str, Any]) -> Envelope`
- `ValidatorFunc`: `(envelope: Envelope) -> bool`
- `ProjectorFunc`: `(envelope: Envelope) -> list[Delta]`
- `HandlerFunc`: `(envelope: Envelope) -> Envelope | None`
- All functions use runtime validation to ensure required fields exist

### Runtime Validation
- `validate_envelope_fields(envelope, required_fields)`: Check required fields exist
- `cast_envelope(envelope, target_type)`: Safe cast with validation
- Type guards in handler filters ensure correct envelope shape
- Validation errors add `error` field rather than throwing exceptions

### Migration Strategy
1. Keep existing handlers working with base `Envelope` type
2. Add runtime validation to all handlers
3. Document expected envelope shapes in docstrings
4. Migrate all code

# How to Build a Working Demo

1. decide on a project structure for event types (should it be <protocol>/event_types/projectors or projectors/type e.g.?) and for handlers (all in one /<protocol>/handlers/ folder?)
1. build a processor in core (process.py) that accepts a series of handler-defined commands with parameters.
1. build reference `params` for an event type with no dependencies (`identity` e.g.) 
1. show it can travel through the event type command, and through handlers, until it is projected and applied.
1. confirm query results contain it
1. build more reference `params` sufficient to create a network that can receive incoming data (a `key` event, a `transit_secret` event, a `network-id`, etc.)
1. complete all handlers required so that we can run a handler-defined command that generates an outgoing envelope that would trigger `send`. collect this outgoing envelope, and modify it to use it as an incoming envelope for test purposes. 
1. build a reference envelope for `receive_from_network` containing an event of a type with no dependencies (similar to the kind a sync response would send, with transit layer encryption and event layer encryption and a signature in keeping with the handler design described below)
2. show it can travel through all handlers and get projected. build each handler and prove the path through that handler at each step.
2. build another reference envelope that depends on the first, send it through first, and confirm it gets projected too after the second envelope arrives and unblocks it. (tests `resolve_deps`)
3. build a `send_sync_requests` command that sends an event of type `sync_request` to the network to test the outgoing pipeline, building any pieces along the way.
1. confirm that `network_simulator` loops it back and that it is received and applied.
1. write a real `sync_request` validator/projector that emits outgoing response envelopes and test that a command like sending a message works given enough execution steps. 
1. add the model from signed groups, with the addition of addresses and transit and event encryption, for invite, users, groups and link-invite and link events
1. begin building tests around all functionality
1. build demo that shows we can invite users, message, create channels, and generally do stuff
1. add support for blobs

Use ideal_protocol_design.md as a guide when necessary, but simplify when possible.  

Use previous_poc as a cheat sheet when implementing handler functionality related to encryption, identity, joining with `user` events, linking, etc. We can use this as a model for the kinds of handlers, though what we are building is a bit more complex because its networking model (with real addresses and transit enc) is more complex.

# Future Work

## Raw Store Pattern (Quarantine Area)

Consider implementing a two-phase storage pattern:

1. **RAW store** (after transit decrypt): `events_raw` keyed by event_id
   - Always dedupe on event_id
   - Never write plaintext here
   - Limited retention (TTL, size quotas)
   - Drop rows that never validate after N retries / T hours

2. **VALIDATED store** (after check_sig + validate): `events_validated`
   - Includes rid, event_type, plaintext, etc.
   - Promote from RAW→VALIDATED when validation passes
   - resolve_deps queries events_validated

**Operational guardrails:**
- Never persist resolved_local (private keys, group keys, prekeys) in any table
- Keys only live in memory