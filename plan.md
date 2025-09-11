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

How to proceed:

1. decide on a project structure for event types (should it be <protocol>/event_types/projectors or projectors/type e.g.?) and for handlers (all in one /<protocol>/handlers/ folder?)
1. build reference `params` for an event type with no dependencies (`identity` e.g.) 
1. show it can travel through the event type command, and through handlers, until it is projected and applied.
1. confirm query results contain it
1. build more reference `params` sufficient to create a network that can receive incoming data (a `key` event, a `transit_secret` event, a `network-id`, etc.) 
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

Use previous_poc (poc-3) as a reference for how to implement things when helpful, noting that there will be radical differences.

# Pipelines

Handlers use filters to subscribe to the eventbus. We use these to create pipelines. 

## Incoming Pipeline:

- `receive_from_network` processes envelopes from the network interface with origin_ip, origin_port, received_at, and raw_data and emits envelopes with transit_key and transit_ciphertext
- `resolve_deps` processes all envelopes where `deps_included_and_valid` is false or `unblocked: True` and and emits envelopes with `missing_deps: True` and a list of missing deps, or with `deps_included_and_valid: True`, with all of the deps included in the envelope, pulling deps only from already-validated events and ignoring not-yet-validated events. Keys are revered to by hash of event and resolved with any other deps. 
- `decrypt_transit` consumes envelopes with `deps_included_and_valid` and `transit-key-id` and `transit_ciphertext` and no `event-key-id` or `event-ciphertext`, and uses the included `transit-key-id` dep which includes its validated envelope (which in turn includes the unwrapped secret and `network-id`) (from `resolve_deps`) to decrypt the `transit_ciphertext` and add `transit-plaintext` and the `network-id` associated with the key, and the `event_key_id` and `event_ciphertext`, and the `event_id` (blake2b hash of event ciphertext) to the emitted envelope.
- `remove` consumes envelopes where `event_id` exists and `should_remove` is not false, calls all Removers for each event type, and drops/purges the envelope if any returns True, else it emits the envelope with `should_remove: False` 
- `unseal_key` consumes envelopes where `deps_included_and_valid` and `should_remove: False` and the `event_key_id` is a `peer-id` with a public key, and it emits an envelope with a `key` event_type, its `key_id` (hash of the event), and its unsealed secret, and `group-id`.    
- `decrypt_event` consumes envelopes where `deps_included_and_valid` and `should_remove: False` the `event_key_id` points to a `key_id` and `event_plaintext` is empty and emits envelopes with a full `event_plaintext` extracting the `event_type` and adding that to the envelope too

*note that `deps_included_and_valid` gets reset to false by any handler that adds deps* 

- `check_sig` consumes envelopes where `sig_checked` is false or absent, with their full `peer-id` dep (the public key they claim to be signing with), and emits envelopes with `sig_checked: True` if the signature verifies, and adds an error message to the envelope if not. *note that we check sigs on key events too* 
- `check_group_membership` consumes envelopes with a `group-id` where `is_group_member` is false or absent. All events with `group-id` also include `group-member-id` which points to a valid `group-member` event adding them as a member and checks that the `user_id` of the event matches the `group_member_id` and that `group_member_id` matches `group_id`. Then it emits an envelope with `is_group_member: True`
- `prevalidate` consumes envelopes with `event_plaintext`, `event_type`, `sig_checked: True`, `is_group_member: True` and it emits envelopes with `prevalidated: True`.
- `validate` consumes `prevalidated` events, uses a validator for the corresponding event type as a predicate, and emit envelopes with `validated: True` and all event data in the envelope
- `unblock-deps` consumes all `validated` events and all `missing_deps` events and keeps a SQL table of `blocked_by` and when it consumes an event whose id is in `blocked_by` it emits the event with `unblocked: True`. 
- Projectors for each event type consume all `validated` envelopes for that event type, call apply(deltas) and emit envelopes with `projected: True` and deltas (`op: ___`)

## Creation Pipeline

- Creators consume `params` and emit unsigned, plaintext events in envelopes that have `self_created:true`
- `sign` consumes envelopes with `self_created:true`, adds a signature to the event, and emits envelopes with `selfSigned: True` 
- `resolve_deps` (same as above) processes all envelopes where event`deps_included_and_valid` is falsy or `unblocked: True` and and emits envelopes with `missing_deps: True` and a list of missing deps, or with `deps_included_and_valid: True`, with all of the deps included in the envelope, pulling deps only from already-validated events and ignoring not-yet-validated events. Keys are revered to by hash of event and resolved with any other deps.
- All other checks same as create from here to `validated`
- `gossip` consumes `validated` `self_created` events and sends them to outgoing, to recently seen peers (optional: skip for now and define more later) 

## Outgoing Pipeline

- Handlers that send events (sync-request, e.g.) emit envelopes with `outgoing:True`, and all of these as unresolved dependencies: `event-id`, `due_ms`, `network-id`, `address_id`, `user-id`, `peer-id`, `key_id` and `transit_key_id` (so they can control timing of send) with `deps_included_and_valid` as false. 
- `resolve_deps` consumes `deps_included_and_valid: False` and emits with all dependencies including with all this dep data including `dest_address`, `dest_port`, `event_plaintext`, `event_ciphertext` (if available e.g. if not a newly created event being gossipped) and emits with `deps_included_and_valid: True`
- `check_outgoing` consumes envelopes with (`outgoing:True` AND `deps_included_and_valid: True`) and without `outgoing_checked` and ensures that `address_id`, `peer_id`, and `user_id` all match and emits envelope with `outgoing_checked: True`
- `encrypt_event` consumes envelopes with `outgoing_checked` and no `event_ciphertext` (if there are any) and emits an envelope with no event `plaintext` or `secret` and event `event_ciphertext` and `event_key_id` 
- `encrypt_transit` consumes envelopes with `outgoing_checked` and `ciphertext` and `transit_key_id` and `transit_secret` and emits an envelope with no `event_plaintext` or `event_ciphertext` or secret or `event_key_id` or `transit_secret` and only `transit_ciphertext` and `transit_key_id`
- `strip_for_send` consumes events with `transit_ciphertext` and ensures they consist only of `transit_ciphertext`, `transit_key_id`, `due_ms`, `dest_ip`, `dest_port` and `stripped_for_send: True` and are not of an event type that should never be shared e.g. `identity_secret` or `transit_secret`
- `send_to_network` consumes events with `stripped_for_send: True` and sends them using a framework-provided function send(stripped_envelope)

## Network Simulator

- `network_simulator` when present also consumes envelopes with `stripped_for_send: True` and envelopes with realistic data for `receive_from_network` incrementing time to simulate latency. (This requires a network design that can differentiate incoming data and route to proper networks/identities)

# Event Types

Each event type has a validator, a projector, a creator, a reader, and a remover. Readers are for queries. Removers are for deletion or user removal.

# API

The framework consumes an openapi.yaml file that names creators and reader operations, and wires up an API.

# Crypto

The framework provides crypto functions hash, kdf, encrypt, decrypt, sign, check_sig, seal, unseal that all handlers and event type commands, projectors, etc. can use. 

# Testing

- **validator:** valid envelopes return true and invalid ones return false
- **command** given params emit the correct envelopes
- **projector** envelopes return correct envelopes (with deltas)
- **handler** consumes/ignores the correct envelopes (filter test) and emits the expected envelope for a given consumed envelope
- **query** given a series of deltas on a fresh database, query result matches expected (we test with a real SQLite database)
- **remover** given a list of *all* removed event-id's and state, does it return True for envelopes that should be removed? (e.g. a `message-id` with a removed channel's `channel-id`) 

Testing infra-specific handlers:

- **send_to_network:** must provide correct params to send(params) function for a given envelope

Testing infra

- **apply(deltas):** given a db state and deltas, the final state is correct (use db seeder and db snapshots so that states can be expressed, compared as json)
- **receive(raw_network_data):** given some unit of raw network data from an ip and port, creates envelopes with `origin_ip`, `origin_port`, `received_at`, and `raw_data`
- **crypto:** basic functional tests of all crypto functions