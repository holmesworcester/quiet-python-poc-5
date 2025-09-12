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
- The only envelope id is encrypted_event_id (blake2b of hash of event ciphertext). Many envelopes (transit e.g.) will not have id's for some part of their lifecycle.  
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
2. Fetches each dependency from validated events
3. Adds them to `resolved_deps`:
```python
envelope["resolved_deps"] = {
    "identity:identity_abc123": {
        "event_plaintext": {"type": "identity", "peer_id": "..."},
        "local_metadata": {"private_key": "..."}  # Included for identities
    }
}
```

Subsequent handlers can then use resolved dependencies as pure functions without database access.

## Local Metadata

`local_metadata` is envelope data that:
- Contains sensitive local information (e.g., private keys)
- Is never sent over the network
- Is included when resolving dependencies for local operations
- Is stored locally but stripped by the strip_for_send handler before transmission

# Pipelines

Handlers use filters to subscribe to the eventbus. We use these to create pipelines. 

## Incoming Pipeline:

- `receive_from_network` processes envelopes from the network interface with origin_ip, origin_port, received_at, and raw_data and emits envelopes with transit_key and transit_ciphertext
- `resolve_deps` processes all envelopes where `deps_included_and_valid` is false or `unblocked: True` and and emits envelopes with `missing_deps: True` and a list of missing deps, or with `deps_included_and_valid: True`, with all of the deps included in the envelope, pulling deps only from already-validated events and ignoring not-yet-validated events. Keys are revered to by hash of event and resolved with any other deps. 
- `decrypt_transit` consumes envelopes with `deps_included_and_valid` and `transit-key-id` and `transit_ciphertext` and no `event-key-id` or `event-ciphertext`, and uses the included `transit-key-id` dep which includes its validated envelope (which in turn includes the unwrapped secret and `network-id`) (from `resolve_deps`) to decrypt the `transit_ciphertext` and add `transit-plaintext` and the `network-id` associated with the key, and the `event_key_id` and `event_ciphertext`, and the `event_id` (blake2b hash of event ciphertext) to the emitted envelope. It emits another identical envelope with `write_to_store: True`.
- `remove` consumes envelopes where `event_id` exists and `should_remove` is not false, calls all Removers for each event type, and drops/purges the envelope if any returns True, else it emits the envelope with `should_remove: False`.
- `unseal_key` consumes envelopes where `deps_included_and_valid` and `should_remove: False` and the `event_key_id` is a `peer-id` with a public key, and it emits an envelope with a `key` event_type, its `key_id` (hash of the event), and its unsealed secret, and `group-id`. It emits another envelope with `write_to_store: True`.
- `decrypt_event` consumes envelopes where `deps_included_and_valid` and `should_remove: False` the `event_key_id` points to a `key_id` and `event_plaintext` is empty and emits envelopes with a full `event_plaintext` extracting the `event_type` and adding that to the envelope too. It emits another identical envelope with `write_to_store: True`.
- `event_store` consumes envelopes with `write_to_store: True` and saves them.

*note that `deps_included_and_valid` gets reset to false by any handler that adds deps* 

- `check_sig` consumes envelopes where `sig_checked` is false or absent, with their full `peer-id` dep (the public key they claim to be signing with), and emits envelopes with `sig_checked: True` if the signature verifies, and adds an error message to the envelope if not. *note that we check sigs on key events too* 
- `check_group_membership` consumes envelopes with a `group-id` where `is_group_member` is false or absent. All events with `group-id` also include `group-member-id` which points to a valid `group-member` event adding them as a member and checks that the `user_id` of the event matches the `group_member_id` and that `group_member_id` matches `group_id`. Then it emits an envelope with `is_group_member: True`
- `prevalidate` consumes envelopes with `event_plaintext`, `event_type`, `sig_checked: True`, `is_group_member: True` and it emits envelopes with `prevalidated: True`.
- `validate` consumes `prevalidated` events, uses a validator for the corresponding event type as a predicate, and emit envelopes with `validated: True` and all event data in the envelope.
- `unblock-deps` consumes all `validated` events and all `missing_deps` events and keeps a SQL table of `blocked_by` and when it consumes an event whose id is in `blocked_by` it emits the event with `unblocked: True`. 
- Projectors for each event type consume all `validated` envelopes for that event type, call apply(deltas) and emit envelopes with `projected: True` and deltas (`op: ___`)

## Creation Pipeline

- Creators consume `params` and emit unsigned, plaintext events in envelopes that have `self_created:true` and a `deps` array listing required dependencies (e.g. `["identity:abc123"]` for signing)
- `resolve_deps` (same as above) processes all envelopes where `deps_included_and_valid` is falsy or `unblocked: True` and emits envelopes with `missing_deps: True` and a list of missing deps, or with `deps_included_and_valid: True`, with all of the deps included in the envelope under `resolved_deps`, pulling deps only from already-validated events and ignoring not-yet-validated events. Keys are referred to by hash of event and resolved with any other deps.
- `sign` consumes envelopes with `self_created:true` and `deps_included_and_valid: True`, extracts the identity's private key from `resolved_deps`, adds a signature to the event, and emits envelopes with `selfSigned: True` 
- All other checks same as create from here to `validated`
- `encrypt_event` consumes envelopes with `outgoing_checked` or `validated` and no `event_ciphertext` and emits an envelope that adds `event_ciphertext` and `event_key_id` and `write_to_store: True` 


## Outgoing Pipeline

- Handlers that send events (sync-request, e.g.) emit envelopes with `outgoing:True`, and all of these as unresolved dependencies: `event-id`, `due_ms`, `network-id`, `address_id`, `user-id`, `peer-id`, `key_id` and `transit_key_id` (so they can control timing of send) with `deps_included_and_valid` as false. 
- `resolve_deps` consumes `deps_included_and_valid: False` and emits with all dependencies including with all this dep data including `dest_address`, `dest_port`, `event_plaintext`, `event_ciphertext` (if available e.g. if not a newly created event being gossipped) and emits with `deps_included_and_valid: True`
- `check_outgoing` consumes envelopes with (`outgoing:True` AND `deps_included_and_valid: True`) and without `outgoing_checked` and ensures that `address_id`, `peer_id`, and `user_id` all match and emits envelope with `outgoing_checked: True`
- `encrypt_event` consumes envelopes with `outgoing_checked` or `validated` and no `event_ciphertext` (if there are any) and emits an envelope with no event `plaintext` or `secret` and event `event_ciphertext` and `event_key_id` 
- `encrypt_transit` consumes envelopes with `outgoing_checked` and `ciphertext` and `transit_key_id` and `transit_secret` and emits an envelope with no `event_plaintext` or `event_ciphertext` or secret or `event_key_id` or `transit_secret` and only `transit_ciphertext` and `transit_key_id`
- `strip_for_send` consumes events with `transit_ciphertext` and ensures they consist only of `transit_ciphertext`, `transit_key_id`, `due_ms`, `dest_ip`, `dest_port` and `stripped_for_send: True` and are not of an event type that should never be shared e.g. `identity_secret` or `transit_secret`
- `send_to_network` consumes events with `stripped_for_send: True` and sends them using a framework-provided function send(stripped_envelope)

## Network Simulator

- `network_simulator` when present also consumes envelopes with `stripped_for_send: True` and envelopes with realistic data for `receive_from_network` incrementing time to simulate latency. (This requires a network design that can differentiate incoming data and route to proper networks/identities)

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

# Command creates envelope with dependencies
envelope = create_message(params, db)
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