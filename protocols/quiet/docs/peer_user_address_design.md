# Peer, User, and Address Event Design

## Overview

This document describes the separation of identity, peer, user, and address concerns in the Quiet protocol, following the ideal protocol design patterns.

## Core Concepts

### 1. Identity Event
- Represents a cryptographic identity (keypair)
- Contains: `name`, `network_id`
- Does NOT contain identity_id (it's the hash of the event)
- Self-signing (no dependencies)
- Stores private key and public key as secret in envelope, which is never shared
- The public key is used for signing but is in the envelope, not the event

### 2. Peer Event
- Represents the combination of identity + device
- Contains: `public_key` (of the identity), `network_id`, `created_at`
- Does NOT contain peer_id (it IS the peer_id once hashed)
- The public_key links it to its identity
- No device_id or device_name - the peer IS the device
- Signed by the identity it represents (via envelope peer_id which is the public key)
- Multiple peers can exist for the same USER (not same identity)
- Identity is the private part of peer that's not shared but important locally

### 3. User Event
- Represents a user account in a network (via invite)
- Contains: `peer_id` (of creating peer), `name`, `network_id`, `group_id`, `invite_pubkey`, `invite_signature`
- Does NOT contain user_id (it's the hash of the event)
- Created when joining via invite
- The peer_id in the event is the initial peer that created this user
- This peer is automatically linked (no separate link_invite needed at join time)

### 4. Link-Invite Event
- Links additional peers to an existing user account
- Contains: `peer_id`, `user_id`, `network_id`
- Does NOT contain link_id (it's the hash of the event)
- Actually two events: link_invite (root) and link (references link_invite)
- Dependencies: peer and user must exist
- Signature checked against peer's identity public key
- Used for multi-device support after initial join

### 5. Address Event
- Announces network address for a peer
- Contains: `peer_id`, `user_id`, `address`, `port`, `network_id`, `timestamp`
- Does NOT contain address_id (it's the hash of the event)
- Ephemeral - can be updated frequently
- Allows peers to find each other on the network

## Event Flow

### Joining a Network (First Device)

The `join_network` command creates three events:

1. **Create Identity**
   ```
   identity_event = {
     type: "identity",
     identity_id: <public_key>,
     name: "Alice",
     network_id: <network_id>
   }
   ```

2. **Create Peer** (identity on this device)
   ```
   peer_event = {
     type: "peer",
     identity_id: <public_key>,
     network_id: <network_id>
   }
   # peer_id = hash(peer_event) - filled by handler
   ```

3. **Create User** (via invite)
   ```
   user_event = {
     type: "user",
     peer_id: <hash_of_peer_event>,
     name: "Alice",
     network_id: <network_id>,
     group_id: <from_invite>,
     invite_pubkey: <derived_from_secret>,
     invite_signature: <proof>
   }
   # user_id = hash(user_event) - filled by handler
   # The peer that creates the user is automatically linked
   ```

5. **Announce Address** (when online)
   ```
   address_event = {
     type: "address",
     address_id: <hash>,
     peer_id: <public_key>,
     user_id: <user_id>,
     address: "192.168.1.100",
     port: 8080,
     network_id: <network_id>,
     timestamp: <now>
   }
   ```

### Adding Second Device (Same User)

1. **Create Identity** on new device
2. **Create Peer** for new device
3. **Link to Existing User** via link_invite (using shared secret or QR code)
4. **Announce Address** for new peer

## Benefits

1. **Multi-device Support**: Users can have multiple devices (peers) sharing the same user account
2. **Device Management**: Can revoke individual devices without affecting user account
3. **Network Flexibility**: Address changes don't require new events, just update address events
4. **Clear Separation**: Identity (crypto), Peer (device), User (account), Address (network)
5. **Migration Support**: Can move user account to new device by creating new peer and link

## Implementation Changes Needed

### New Event Types
- [ ] Create `peer` event type with commands, validator, projector, schema
- [ ] Create `link_invite` event type with commands, validator, projector, schema
- [ ] Create `address` event type with commands, validator, projector, schema

### Update Existing Events
- [ ] Remove `peer_id` from `user` event (only in link_invite)
- [ ] Remove address/port from all events (only in address event)
- [ ] Update `join_network` to create peer, user, and link_invite events

### Schema Changes
- [ ] Add `peers` table
- [ ] Add `link_invites` table
- [ ] Add `addresses` table
- [ ] Update `users` table (remove peer_id, address, port)

### Query Updates
- [ ] Update user queries to join with link_invites to find peers
- [ ] Add peer queries
- [ ] Add address queries for finding online peers

## Migration Path

1. Keep existing commands working initially
2. Add new event types one by one
3. Update join_network to use new flow
4. Update queries to use new tables
5. Remove deprecated fields from old events

## Event Cross-Reference Solution

### Problem
When commands create multiple events that reference each other (e.g., join_network creates identity, peer, and user events), we need a way to handle cross-references since event IDs are only generated after signing/hashing.

### Solution: Placeholder References with Multi-Pass Pipeline
Commands can output events with placeholder references that get resolved by the pipeline in multiple passes:

**Special case - Identity events**:
- Identity events are local-only and don't need signing
- Commands can calculate identity_id directly: `hash(canonical_event)`
- This allows peer events to reference identity_id immediately

1. **Commands emit placeholders**:
   ```python
   # In join_network command:
   user_event = {
       'type': 'user',
       'peer_id': '@generated:peer:0',  # Placeholder for first peer event's ID
       'network_id': network_id,
       ...
   }
   ```

2. **Pipeline processes in multiple passes**:
   - **Pass 1**: Process events without placeholders (identity, peer)
     - These go through resolve_deps → signature → get event_id
     - Pipeline tracks generated IDs
   - **Pass 2**: Process events with placeholders (user)
     - Pipeline substitutes `@generated:` placeholders with actual IDs
     - Then these go through normal pipeline

3. **Alternative: Late-binding in signature handler**:
   - Signature handler could resolve placeholders just before signing
   - It has access to all previously generated event_ids in the batch
   - Replaces `@generated:peer:0` with actual peer_id
   - Then signs the event with correct references

4. **Benefits**:
   - General solution for any multi-event command
   - Works for message + message-link-unfurl
   - Works for peer → user → link_invite chains
   - Queries only run after all events are processed

### Implementation Plan
1. Modify pipeline to handle multi-pass processing OR
2. Update signature handler to resolve `@generated:` placeholders
3. Update join_network to use placeholders
4. Test with multi-event commands

## Questions to Resolve

1. How do we handle peer key rotation?
2. Should addresses expire after a timeout?
3. How do we handle NAT traversal hints in address events?
4. Should we have a separate event for revoking peer access?