# Flows Plan and Identity-as-Event Refactor

This document lays out the plan to:
- Re-introduce Identity as a protocol event (local-only), removing core identity special-casing.
- Add flows as first-class, reusable, read-only orchestrations (query → emit → return).
- Make API exposure explicit and simple via api.py, backed by flows/commands/queries.
- Allow jobs and reflectors to reuse flows, and optionally collapse them into a single flows-first approach.

## Objectives
- Single mental model: Commands emit events; Queries read; Projectors emit deltas for core to write state; Flows orchestrate by calling commands/queries and returning data.
- Identity becomes a normal event (local-only) that can be referenced as a dependency (e.g., by peer), removing the need for core identity special handling.
- API surface is explicit and small: only operations declared in api.py are exposed.
- Reuse the same flows design for API, jobs, and reflectors to avoid duplicated logic.

---

## Phase 1 — Make Identity an Event Again

Identity becomes a protocol event type that is:
- Local-only (never sent to the network).
- Exempt from signing and external verification.
- The projector persists private key material into the protocol’s identities table (local storage).
- Usable as a dependency (e.g., peer depends on identity).

### Event Definition (protocols/quiet/events/identity)
- Event type: `identity`
- Plaintext fields (minimum):
  - `type: 'identity'`
  - `identity_id: str` (derived from public key; or allow the crypto handler to compute deterministically)
  - `name: str`
  - `public_key: hex`
  - `private_key: hex` (local secret)
  - `created_at: int`
- Envelope flags:
  - `local_only: True` (skip sending to network)
  - `store_as_identity: True` (projector will write to identities; event_store should skip)
  - `self_created: True` (created by this node)

### Handler updates
- signature.py
  - Continue to skip signing identity events.
  - For signing non-identity events: use full identity event from deps.
  
- resolve_deps.py
  - Add inferred plaintext dependency for `peer` on `identity` when `identity_id` is present in the corresponding peer event.
  - When resolving, include the identity dependency in `resolved_deps` so the signature handler can sign using local identity keys.

- project.py (new identity projector)
  - On `identity` events, insert into `identities` table (protocol-level) with both public_key and private_key.
  - Never project to shared/global state tables

- event_store.py
  - Already skips identity events when `store_as_identity` is set. Ensure this path is used. # How will resolve_deps have it if it isn't in the event store. I think we should have a local-only flag on event-store events and store it there, no?

- send_to_network.py
  - Skip envelopes with `local_only: True`.

- crypto.py
  - Identity events still receive a deterministic `event_id` (enc_id). Implementation options:
    - Use the canonical JSON bytes (but do not encrypt) as `event_ciphertext` so `enc_id` is computed without leaking private keys externally.

### Remove identity from core
- core/identity.py
  - Deprecate identity creation/storage APIs and `sign_with_identity` lookup.
  - Replace `sign_with_identity` usage by a protocol-side lookup (sign handler queries protocol identities table by public_key → private_key).
- DB migration path
  - On init, migrate existing rows from `core_identities` to protocol identities table if present. # Note: do not worry about migration. We are prototyping. We can reset db's ourselves when we run demo.
  - Keep a compatibility read path short-term if needed (feature-flagged).

### Commands
- identity.create_identity (protocol event command)
  - Emits a local-only identity event with the keypair and name.
- peer.create_peer
  - Require `identity_id` param; remove reliance on core identity.
  - Include `identity_id` in the peer plaintext so resolve_deps can infer `identity:...` dependency. # Command should just emit the envelope with the contents it has. We should get the id back from the crypto handler after it is stored like everything else we emit.  
- Update any command wrappers to align with new sources of identity.

### Tests & scenarios impacted
- Replace usages of `core.identity_create` with the new `identity.create_identity` command or with a flow that wraps both identity + peer.
- Adjust tests to expect identity as an event (local-only) and to verify signing works via protocol-side identity storage.

---

## Phase 2 — Introduce Flows

Flows are read-only orchestrations that can:
- Query: read from DB using existing query functions.
- Emit: call commands to emit envelopes and run them through the pipeline.
- Return: a result dict (e.g., ids + data) and optionally next-state for schedulers.

### Structure
- `protocols/quiet/events/<event>/flows.py`
  - Define small, typed functions: `(params: TypedDict, ctx: FlowCtx) -> TypedDict`
- FlowCtx contains:
  - `db_ro`: read-only DB connection (wrapper); chains must not write directly.
  - `runner`: pipeline runner for emitting envelopes.
  - `protocol_dir`, `request_id`.
- Helpers:
  - `emit(ctx, 'event.create_x', params) -> event_id|ids` — runs a command through the runner and returns IDs.
  - `query(ctx, 'event.get', params) -> data` — calls the query registry directly.

### API exposure
- Prefer a protocol-level file for clarity: `protocols/quiet/api.py`
  - Explicitly expose the public operations and map them to flows/commands/queries:
    - Example: `EXPOSED = {'user.join_as_user': user_flows.join_as_user, 'message.create_message': message_commands.create_message, 'message.get': message_queries.get}`
  - Only operations listed here are accessible via APIClient.
  - Optional: per-op `route` metadata for future HTTP/OpenAPI adapters.

### Typechecking
- Keep and expand TypedDicts in `protocols/quiet/client.py` for param/result shapes.
- Flows functions can be annotated with these types; `api.py` exposes ops with references to typed callables.
- API wrappers in `client.py` call `api.execute_operation(op_id, params)` and cast to the expected result type — consistent with current pattern and mypy-friendly.

### Example flow: user.join_as_user
- Precondition: caller passes `identity_id` (identity is created via identity.create_identity command first), or the flow can emit `identity.create_identity` (still read-only from the flow’s perspective: it only emits; side effects happen in the pipeline).
- Steps:
  - `peer_id = emit(ctx, 'peer.create_peer', { identity_id, username })`
  - `user_id = emit(ctx, 'user.create_user', { peer_id, network_id, group_id, name, invite_pubkey, invite_signature })`
  - `return { 'ids': { 'identity': identity_id, 'peer': peer_id, 'user': user_id }, 'data': {...} }`

---

## Phase 3 — Jobs and Reflectors via Flows (optional, later)

We can unify jobs and reflectors by reusing flows as the only “do things” abstraction:
- Jobs: protocol-level `jobs.py` lists schedules and the flow to run with params; the scheduler executes the flow and persists returned next-state.
- Reflectors: projectors can optionally trigger a flow (or both project and trigger) by emitting a small control envelope or directly invoking a flow adapter:
  - Example: on `sync_response` projection, call `flows.blob.sync_fetch_missing(...)`.

This collapses surface area to:
- Commands, Queries, Projectors, Flows, API (exposed).
- Jobs and Reflectors become thin: they declare “when” and “with what params,” then call flows.

### Saving last-run state
- Flows can persist last-run state by emitting deltas through a small local-state projector (e.g., `flow_state` table keyed by flow name + params hash).
- Alternatively, return `next_state` in the flow result; the job runner writes it back to its own store.

---

## Phase 4 — APIClient changes

- Discovery:
  - Load `protocols/quiet/api.py` and build an operation map from its `EXPOSED` dict (or decorated functions).
  - For each exposed op, store type metadata (if provided) for optional runtime validation.
- Execution:
  - Build `FlowCtx` (`db_ro`, `runner`, `protocol_dir`, `request_id`) and invoke the flow/command/query callable.
  - Return the result dict directly (flows do not use response handlers).
- Compatibility:
  - Keep support for direct commands/queries during migration; later, warn or disable if not listed in `api.py`.

---

## Phase 5 — Migration Plan (Step-by-step)

1) Identity as Event
- Add `events/identity` with command, validator (minimal), projector, and tests.
- Update signature handler to use protocol identities table for signing.
- Update resolve_deps to add identity dep for peer.
- Update peer.create_peer to require `identity_id` param.
- Migrate data from `core_identities` into protocol identities table on init (one-time).
- Remove usages of `core.identity_create` in tests and scenarios.

2) API minimal exposure
- Create `protocols/quiet/api.py` with EXPOSED operations.
- Update APIClient to discover and use only these operations by default (keep fallback behind a flag during migration).

3) Introduce flows
- Add FlowCtx + helpers (emit/query) in core.
- Create `events/<event>/flows.py` and move `join_as_user` orchestration there.
- Expose it via `api.py` and update client wrappers to point to the same op id.

4) Stabilize + tests
- Ensure scenario tests (e.g., multi-identity chat) pass using the new identity event and flows.
- Update handler-level tests where they assumed core identity state.

5) (Optional later) Jobs/Reflectors over flows
- Add protocol-level `jobs.py` that lists flows + schedule + params.
- Provide a small job runner that calls flows and handles returned next-state.
- Allow projectors to optionally trigger flows (or emit a “run_flow” control envelope consumed by an ops handler).

---

## Open Questions & Decisions
- Identity event `event_id` derivation: use canonical plaintext JSON bytes (local-only) vs. run through crypto to compute `enc_id`? Favor consistency with other events (enc_id), but never send.
- Where to store private key: dedicated protocol identities table (preferred), not the generic events table. projector handles write and scrubs from envelope if desired.
- API routes: keep as optional metadata in `api.py` for future HTTP adapter; not needed for in-process APIClient.
- Type metadata: keep using TypedDicts in `protocols/quiet/client.py`; optionally attach to exposed ops for runtime validation / OpenAPI gen later.
- Compatibility window: keep core identity signer as a fallback until migration completes (feature-flag or version gate).

---

## Summary
- Normalize identity as an event again (local-only, never sent) so peer and others can depend on it, and signature can reliably find keys.
- Introduce flows as simple, read-only orchestrations callable from API (and later jobs/reflectors).
- Make API explicit via `api.py`, reducing accidental surface and improving clarity.
- Converge jobs/reflectors onto flows to avoid duplicated orchestration logic and simplify mental model.
