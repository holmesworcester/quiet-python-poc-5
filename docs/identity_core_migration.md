# Identity as Core Feature - Migration Plan

## Current State
- Identity has been moved to core framework (`core/identity.py`)
- Identity events are no longer created or stored in the events table
- Signature handler uses core identity for signing self-created events
- Many events still expect `peer_id` references but we're using `identity_id` directly

## Problems
1. **Peer events not being created consistently**
   - `join_as_user` creates peer events
   - `create_network` doesn't create peer events
   - Messages expect `peer_id` but don't have peer events to reference

2. **Field naming inconsistency**
   - Some events use `identity_id` for signing
   - Some events use `peer_id` for author/creator references
   - Registry expects `peer_id` for messages but commands use `identity_id`

3. **Dependency resolution complexity**
   - Trying to resolve `peer:identity_id` as a special case
   - This creates unnecessary complexity in resolve_deps handler

## Proposed Solution

### Option 1: Always Create Peer Events
When an identity is used on a network, always create a peer event:
- Peer events represent an identity's presence on a network
- All events reference the peer event ID, not the identity directly
- This maintains the original protocol design

**Pros:**
- Clean separation: identity (core) vs peer (protocol)
- No special cases in dependency resolution
- Maintains existing event relationships

**Cons:**
- Extra event creation overhead
- Need to track peer event IDs for each identity/network combination

### Option 2: Remove Peer Events Entirely
Since identity is now core, eliminate peer events:
- All events reference `identity_id` directly
- Update all validators/projectors to use `identity_id`
- Simplify the event model

**Pros:**
- Simpler model
- No need to track peer events
- Direct identity references

**Cons:**
- Major protocol change
- Loses device/identity distinction
- Breaks existing event relationships

### Option 3: Peer Events Only for Remote Identities
- Local identities (core) don't need peer events
- Only create peer events for remote users joining via invites
- Local events use `identity_id`, remote events use `peer_id`

**Pros:**
- Optimized for local vs remote distinction
- Reduces unnecessary event creation

**Cons:**
- Inconsistent event model
- Complex validation logic
- Hard to reason about

## Recommendation

**Go with Option 1: Always Create Peer Events**

This maintains the cleanest architecture:
1. Core framework manages identities (private keys, signing)
2. Protocol defines peer events (public presence on network)
3. All protocol events reference peer events consistently
4. No special cases or complex resolution logic

## Implementation Steps

1. **Update network creation** to always create a peer event
2. **Update message creation** to look up the peer event for the identity
3. **Keep peer_id references** throughout the protocol
4. **Store peer event IDs** in a lookup table for quick access
5. **Test** the complete flow

## Key Insight

The core identity is about **authentication** (who can sign).
The peer event is about **authorization** (who is on this network).

Keeping them separate maintains a clean architecture where:
- Core provides cryptographic identity
- Protocol defines network membership and relationships