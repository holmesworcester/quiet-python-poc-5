# Event-Centric Framework Development Diary

## Initial Setup (Day 1)

### Architecture Decisions
- Implementing event-centric design based on revised understanding
- Everything is a saga with read-write state access
- Minimal framework - most logic lives in sagas
- No special constructs - just events and sagas

### Key Components to Build
1. **Minimal Saga Runtime**
   - Saga functions: `saga(event, db) -> list[Event]`
   - Event routing by type
   - Saga registry

2. **Core Sagas (not framework code)**
   - Event store saga (manages event log)
   - Dependency tracker saga (unblocks events)
   - Delta saga (applies state changes)

3. **Testing Infrastructure**
   - Each saga has saga.json with tests
   - Same pattern as poc-3 handlers
   - Framework tests are a real protocol

### Key Insights from Notes
- Sagas have full read-write database access
- Each saga can have its own schema.sql
- Dependency tracking is just another saga, not framework code
- No envelopes - just plain events
- Delta events have operation in payload, not different types
- Framework should be minimal - sagas do the work

### Initial Learnings
- Event identity via content hash provides natural deduplication
- Sagas manage their own state in database tables
- Everything that would be "framework" is just another saga
- Framework tests are organized as a protocol (protocols/framework_tests) with real sagas

## Next Steps
- Create minimal saga runtime
- Set up framework_tests protocol with basic sagas
- Implement event store as a saga
- Create dependency tracker saga
- Write delta application saga

## Analysis Complete (Current)

### Understanding from plan.md
The plan proposes an envelope-centric design with:
1. **Envelopes** carrying event-related data through pipelines
2. **Handlers** that subscribe to envelopes via filters
3. **Pipelines**: Incoming, Creation, Outgoing, Network Simulator
4. Each handler processes specific envelope traits and emits new envelopes
5. Event types have validators, projectors, creators, readers, removers

### Understanding from ideal_protocol_design.md
The Quiet Protocol is:
1. An E2EE, P2P protocol for team chat (Slack alternative)
2. All data as 512-byte events with fixed-length fields
3. Networks, groups, channels, messages, encryption layers
4. Blocking/unblocking pattern for dependency resolution
5. Transit-layer and event-layer encryption
6. Sync via bloom filters and windows

### Key Architecture Questions

Based on the plan, I need clarification on the following design choices:

**Option 1: Pure Handler/Pipeline Design (as described in plan.md)**
- Handlers subscribe to envelopes with filters
- Each handler emits new envelopes
- Pipelines: receive_from_network → resolve_deps → decrypt_transit → etc.
- Pro: Clear data flow, easy to trace envelope transformations
- Con: More complex than saga approach mentioned in diary

**Option 2: Saga-based Design (as mentioned in initial diary)**
- Everything is a saga with read-write state access
- Sagas: `saga(event, db) -> list[Event]`
- No envelopes, just plain events
- Pro: Simpler, matches POC-3 patterns
- Con: Less clear data flow than pipeline approach

**Option 3: Hybrid Approach**
- Use envelopes internally but implement handlers as sagas
- Sagas transform envelopes: `saga(envelope, db) -> list[Envelope]`
- Pro: Clear pipeline flow + simple saga implementation
- Con: May be overengineered

### Protocol Implementation Questions

1. **Event Storage**: Should we use SQLite from the start or begin with dict-based DB?
2. **Crypto Implementation**: Real crypto (PyNaCl) or dummy crypto for initial development?
3. **Network Simulation**: Implement network_simulator handler early or focus on core pipelines first?
4. **Testing Strategy**: JSON-based tests like POC-3 or different approach?

### Proposed Initial Implementation Path

If we go with Option 1 (pure handler/pipeline):
1. Create envelope type and handler registry
2. Implement basic handlers: receive_from_network, resolve_deps
3. Create identity event type with validator/projector
4. Build test framework with reference params
5. Add crypto handlers progressively

If we go with Option 2 (saga-based):
1. Create minimal saga runtime
2. Implement event store saga
3. Create dependency tracker saga
4. Build identity event type
5. Add encryption sagas

## Implementation Progress (Current)

Decided to go with **Option 1: Pure Handler/Pipeline Design** with real SQL and real crypto.

### Completed
1. ✅ Created envelope type for carrying event data through pipeline
2. ✅ Built handler base class and registry system
3. ✅ Set up SQLite database with proper schema
4. ✅ Implemented crypto utilities using PyNaCl
5. ✅ Created pipeline handlers:
   - receive_from_network - extracts transit layer info
   - decrypt_transit - decrypts using transit keys
   - decrypt_event - extracts plaintext events
   - resolve_deps - handles dependency resolution
   - check_sig - verifies signatures
   - validate - type-specific validation
   - project - applies events to state
6. ✅ Created identity event type (no dependencies)
7. ✅ Successfully tested event flow through pipeline

### Key Design Decisions
- Handlers filter on specific envelope traits
- Each handler emits new/modified envelopes
- No JSON tests - direct pipeline testing
- Real SQLite database from the start
- Real crypto (PyNaCl) for all operations
- Identity events have no dependencies (bootstrap case)

### Next Steps
- Create more event types: key, network, user
- Implement creation pipeline for self-generated events
- Add outgoing pipeline handlers
- Build network simulator
- Implement sync mechanism