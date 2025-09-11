# Quiet Protocol (Early Draft)

This is an attempt to describe an E2EE, P2P protocol for team chat (e.g. Slack) that is feature complete but simple enough to implement as a "weekend" project.

## Why?

Successful p2p apps like Bittorrent and Bitcoin (or more recently, Nostr) have a certain magic: they provide engineers with a clear, oddly powerful target client that can be built in a tangible period of time. People implement them for funsies.

There is practical value in protocols being this simple. Product teams can implement and adapt them in the course of building a product for end users, not just as a full-time moonshot. Security experts or academics can understand their properties and spread this understanding to others. Technical end users can assess them directly. 

A future looms where lines of code are cheap but clarity and trust are expensive. Simplicity seems an important quality for a protocol.

## How? 

On its face designing a simple p2p protocol for a Slack alternative is hard. How can we keep the *entire protocol* as simple as Bittorrent (which only does file transfer) when file transfer is just *one of many* required features?

We have some levers:

1. Instead of insisting on all reasonable features, we do piles of user research and focus on only those features that teams doing sensitive work really seem to need.
2. We make careful design choices to address all platforms (from fetching iOS push notifications to a server) with the same spec.
3. We lean in to statelessness and pure functions to limit exposure to tame the mind-bending concurrency problems of distributing systems. 
6. We design for easy testing and simulation, and provide a complete set of tests.
4. Once we must use some primitive (like event sourcing, set reconciliation, or a database) we "eat the whole cow" and use it for everything.
5. We can give implementers guidance on how to use standard tools to implement the spec, e.g. by expressing the spec as libsodium API calls or SQL queries that work in SQLite or Postgres.

# Introduction

We describe the protocol beginning with [Events](#Events) (how we store, transmit, and reconcile data) and moving into how we achieve specific kinds of functionality like group key agreement ([Groups](#Groups)), [Event-layer Encryption](#Event-Layer-Encryption), [Blobs](#Blobs), and optional server support. We include a [Threat Model](#appendix-f-threat-model) listing security invariants and known weaknesses.

# Events

All data is created, stored, encrypted, transmitted over the wire, buffered, validated, and acted upon as events. Each peer's source of truth is its set of events. An event's BLAKE2b-128 hash is its `id`.

To avoid ambiguity we describe all cryptographic operations as libsodium API calls. In this case:

```
id(evt) = crypto_generichash(16, evt)
```

Duplicate id's are rejected.

## Encoding

All events are 512 bytes and contain fixed-length fields. See [Appendix A: Types and Layouts](#Appendix-A-—-Types-and-Layouts) for all event types and their content.

Except for `slice` events (see: [Blobs](#Blobs)) all events include a signature over their contents:

```
sign(evt, sk)   = crypto_sign_detached(evt, sk)
verify(evt, pk) = crypto_sign_verify_detached(sig, evt, pk)
```

## Blocking and Unblocking

Some events' validity depends on the prior validation of other events. For example, an event that requires admin privileges depends on the event that made the user an admin.

In this case we follow a *Block and Unblock* pattern whenever an event depends on another event or privilege we do not have: when an event depends on one we don't have yet, we mark it "blocked" and then search appropriately for events to *unblock* after validating each new event.

To prevent infinite loops from cyclical dependencies or persistent validation failures, implementations should track a `retry_count` for each event. When an event is unblocked, its retry count is incremented. Events that reach 100 retry attempts are purged from the system rather than being unblocked again.

We can add a `reason_blocked` field to all blocked events for observability, testing, and debugging.

See [Appendix H: Implementation Notes](#appendix-h-implementation-notes) for notes on efficiency.

## Wire Protocol 

Events are small enough to travel between peers as UDP packets. All messages on the wire are encrypted events (see: [Encoding Events](#Encoding-Events) and [Event-Layer Encryption](#Event-Layer-Encryption)).

# Networks

A group of peers securely sharing data (messages, channels, and file attachments) is a "network". 

## Peer Creation

When joining or creating a network, Alice first creates a keypair. This event is specific to the application, the device, and the network. If Alice joins 5 networks in 2 different applications on her phone, she will have 10 such keypairs.  

The public key of a keypair is a `peer-id`.

## Network Creation

To create a network, Alice creates a `group` event with an optional name (see: [Groups](#groups)).

The `event-id` for this `group` event becomes the `network-id` for the new network.

All members of this group are the network's admins.

## Address Publishing

To make her peer reachable on the network, Alice creates an `address` event that includes her `peer-id`, a network transport (e.g. UDP), her network address, and a port. Every peer on the network periodically creates `address` events with their own latest address information. Other peers use the latest `address` events for each peer.

## Invitation

**Note: it is simpler here to just share a secret and use a KDF with deterministic salt to derive the same keypair on both sides.**

To invite users to the network, Alice creates a new PAKE secret and makes an `invite` event with an expiry time, a max number of joiners, and a public key derived from the PAKE secret.

She then generates a Signal-style "invite link" by base64 encoding the PAKE secret, the `network-id`, and a recent `address` event into a URL that can be shared in an out-of-band message or QR code: `https://app.com/join#[encoded-data]`

To be valid, `invite` events must be created by an admin (see: [Groups](#groups)) and name the correct `network-id`.

## Joining

Alice then joins the network. She creates a `user` event that includes a PAKE proof from her own `invite` wrapping her `peer-id` and the `network-id`. See [Joining PAKE](#Joining-PAKE) for details. 

The `event-id` of this `user` event is her `user-id`.

Once Alice provides an invite link to Bob, he creates a peer (see: [Creating a Peer](#creating-a-peer)) and joins using the same process. He then sends his `join` and `address` events to Alice, making as many attempts as needed. 

When Alice receives them, she can send events to Bob too. We have a network!

## Multiple networks

As in Slack and Discord, users may belong to multiple networks for different communities or work contexts. 

Multiple networks are distinguished by the keys used (see [Event-layer Encryption](#Event-layer-Encryption)), so networks can use the same address information in their `address` events.

[Optional servers](#Optional-Servers) can serve many networks without the ability to decrypt messages. 

# Groups

"Groups" are sets of `user-id`'s that can only grow. Peers create a new group with a `group` event that names the first member's `user-id`. 

The `group` event `id` is its `group-id`.

Any admin can add to a group, with `grant` events naming a `group-id` and `user-id`. 

Admins can update the group's name by creating `group-name` events with a `global-counter`. 

To validate a `grant` event, the recipient peer checks that it is signed by an admin. If not, we set its state to "blocked" (see: [Blocking and Unblocking](#blocking-and-unblocking)). If it is, the recipient validates the `grant` event.

## Fixed Groups

In some cases (such as individual or group DMs) we may want fixed-membership groups. Peers can create `fixed-group` events naming up to 20 `user-id`'s, sorted ascending.

`fixed-group` id's can be used interchangeably with `group-id`, except that `grant` events with `fixed-group` id's will be invalid.

# Linking Peers on Multiple Devices

Users often work on multiple devices, e.g. a phone and a laptop. To do this, Bob creates a `link-invite` event with an expiry time, a max number of joiners, and a public key derived from a secret he has created. 

He then provides the secret, his `user-id`, the `network-id` and a recent `address` event to the new device with a URL in a QR code: `https://app.com/join#[encoded-data]`

The new device creates its own new `peer` and creates a `link` event with a PAKE proof wrapping the `user-id` and `network-id`.

Any linked device (`peer`) can update the username or profile information for the `user-id`.

TODO: add something to joining pake and prekeys about linked peers and prekeys.

## Validation

`link-invite` events are valid if signed by the same `peer-id` as the `user-id` or by a previously-linked `peer-id`. 

`link` events are valid with a valid PAKE proof corresponding to any existing `link-invite` event and wrapping the `network` event and the same `peer-id` as the `link` event signer.

Any linked peer can add `update` events to that `user-id` to e.g. update a username or avatar (see: [Updating Events](#updating-events)).

We [block](#blocking-and-unblocking) `link-invite`, `link`, and `user-id` update events that fail validation due to missing `link` permission.

# Encryption

We can now discuss how messages are encrypted between peers.

## Prekey Publishing

For each group and channel (see: [Channels](#channels)) peers periodically replenish short-lived and long-lived `prekey` events including a prekey, the `group-id`, and (if applicable) `channel-id`.

`prekey` events are deleted on ttl but private keys are kept until explicitly deleted (see: [Transit-Layer Encryption](#transit-layer-encryption) and [Forward Secrecy](#forward-secrecy)).

See [Joining PAKE and Prekeys](#joining-pake-and-prekeys) in Appendix D. for details.

## Event-Layer Encryption

For each known `peer-id` belonging to each known `user-id` in a group, Alice chooses a prekey (with a not-expiring-too-soon `ttl`) and creates one `key` event encapsulating a group key to it.

TODO: there are fewer concurrency problems if peers rotate a user key, like the LFA design, because then any peer can update the prekeys and do key rotations and peers. It also cuts down on prekeys. Consider this change.  

```
inner := {
    type: 0x04                // KEM
    peer_pk                 // sender’s Ed25519 (for sig verification)
    count, created_ms, ttl_ms // common bookkeeping
    tagId                     // which ACL this key is for
    prekey_id                 // ID of the recipient's published prekey used (for lookup/deletion)
    sealedKey = crypto_box_seal(G, prekey_pk_recipient)  // Seal to recipient's prekey public (not static pk)
    
    sig64   = crypto_sign_detached(inner[..payload], sk_sender)
}

/* scrub group secret */
sodium_memzero(G, sizeof G);
``` 

She then uses XChaCha20-Poly1305 with a 24-byte nonce and an HMAC identifying the `prekey`.

```
seal(k,n,pt,ad) = crypto_aead_xchacha20poly1305_ietf_encrypt(pt,ad,-,n,k)
open(k,n,ct,ad) = crypto_aead_xchacha20poly1305_ietf_decrypt(-,ct,ad,n,k)
hint64(k,n)     = crypto_auth_hmacsha256(n, k)[0..1]       # TODO: not the first 2 bytes, the whole thing
```

`created_at` and `ttl` live outside this encryption layer so that peers can support lazy loading (see: [Sync](#Sync)). (Because active peers can infer this timestamp from "received at", the metadata leak is insignificant and outweighed by the benefits.)

Senders can re-use previously sent secrets until a new `remove-user` or `remove-peer` event, at which point they must use a new secret. 

Peers in a group know when a `key` event *claims* to share a secret with another peer, but they cannot be sure, so depending on the situation, peers might only trust the `key` events they created themselves. When adding a peer to a group, they can issue the new `key` themselves to be sure.

### Event-Layer Encryption and Invites

`key` events can wrap group secrets to invites, for old history e.g. The `ttl` should be equal to the `ttl` of the invite so that they expire, but invitees can keep them much longer (i.e. until all events that require them are deleted).

### Forward Secrecy

[Transit-Layer Encryption](#transit-layer-encryption) provides strong forward secrecy against an attacker that can surveil the network and later compromise a device. We also must protect deleted or expired messages from being recovered by an attacker who can compromise a *server* and later compromise a device. 

When events are deleted or expire, we mark their associated keys and prekeys (the prekeys their keys were encapsulated to) as "must purge".

Periodically, in one atomic transaction, we create `rekey` events for all *not deleted* events associated with the to-be-purged keys and prekeys, encrypted deterministically to the "clean" (not being purged) key whose `ttl` is minimally greater than the event `ttl`. We then purge the problematic keys and prekeys.

```
new_rekey_ciphertext = seal(new_G, deterministic_nonce = HASH(original_event_id + new_key_id), original_plaintext).

/* scrub working key material */
sodium_memzero(new_G, sizeof new_G);
```

Any `rekey` event whose contents are identical to the original event is valid, and valid `rekey` events replace the original event in every way. If different `rekey` events point to the same event, peers choose the one using the key with the closest (but greater) `ttl` and discard the other. 

Peers that cannot decrypt the original event will not be able to validate `rekey` events; eventually they will expire from the buffer.

Rekeying is more performant if `key` events are not re-used across channels, and if `prekey` events are not re-used by `key` events.

#### Out-of-scope: Forward Secrecy for Not-Yet-Purged Events

Unlike Signal or MLS, we do not pursue Forward Secrecy for not-yet-purged events, since "Slack-like" users typically share historical chats and files with newcomers, and since any device compromise would also compromise these not-yet-purged events.

## Removal

All users must be able to remove peers on lost or stolen devices. Admins must be able to remove both peers and users.

When encrypting a new event, a peer MUST choose a key whose recipient set excludes every user-id and `peer-id` present in any accepted `remove-user` or `remove-peer` event. If no such key exists, it MUST create a fresh key event for all remaining members and use that.

To prevent the removed user from being able to monitor user's online status, all peers must issue new `address` events and switch to them after a short delay to allow for propagation and reconnection. 

To ensure a convergent historical record, events from removed users are still valid. However, peers check their set of `remove-peer` and `remove-user` events and reject any [Transit-layer Encryption](#transit-layer-encryption) handshake or response from removed peers.

If an [optional server](#optional-servers) uses another form of transit-layer encryption (e.g. QUIC) it immediately disconnects from and refuses connections with all removed peers.

### Removing Peers

Any peer can issue a `remove-peer` event naming another `peer-id`. Peers can remove themselves and their linked peers. Admins can remove any peer.

We [blocking and unblocking](#blocking-and-unblocking) `remove-peer` events that are invalid for lack of permission.

### Removing Users

Peers can remove the user they are linked to with a `remove-user` event that names the `user-id`. Admins can remove any user, including other admins and themselves.

We [blocking and unblocking](#blocking-and-unblocking) `remove-user` events that are invalid for lack of permission.

## Post-Quantum

We choose to wait until Post Quantum support exists in libsodium, but the design remains sound: larger PQ signatures can span multiple packets by including an arbitrary number of keys in [Blobs](#Blobs) or by [RS erasure coded](https://en.wikipedia.org/wiki/Reed%E2%80%93Solomon_error_correction) keys spanning sufficient events as to be reliable. Events [Blocking and Unblocking](#blocking-and-unblocking) until sigs arrive. Once libsodium ships hybrid HPKE and ML-DSA, we replace X25519 with X25519∥Kyber and drop the legacy Ed25519 field.

# Sync

To sync events (e.g. messages) they don't have, peers create a sync event containing a "window" describing a range of ~100 events and a small bloom filter. (Bloom filters have false positive rates, so some events could fail to sync forever if we did not limit our search)

The responder replies with all events in the window that fail to match the bloom filter. If the transport is UDP, the responser extracts IP and port from the UDP header and replies to that. Dropped or duplicate events affect performance but not reliability. Events sync eventually.

It is useful to sync auth-related events like keys and groups as quickly as possible. We can do this by sending a `sync-auth` event with its own bloom and window. This ensures all received messages can be decrypted, outgoing messages can be encrypted to the most recent set of member peers that peer has access to, and network-wide `remove-user` or `remove-peer` events are received as soon as possible. See: [Appendix D: Auth-Related Events]()

To "lazy load" recent messages, we can send `sync-lazy` events with a `bloom` and a `cursor` identifying which message to start at. The recipient responds with the 100 events prior to the cursor, sorted by `created_at`. `sync-lazy` events do not include a separate window: the `cursor` and the 50 events are the window. 

See [Appendix A: Types and Layouts](#Appendix-A-—-Types-and-Layouts) and [Event-layer Encryption](#Event-layer-Encryption) for the contents of sync events and how they are encrypted.

See: [Window Strategy](#window-strategy) in [Appendix H - Implementation Notes](#appendix-h-implementation-notes) for how state is tracked and windows are created.


## Informal Convergence Proof 

Our Bloom is 512 bits (64 bytes), ~100 IDs and k = 5 hashes. Probability a single test wrongly says “present” is:

`FPR ≈ 0.03  (≈ 3 %)`

Missed items in one pass will surface on the next pass with probability
`p = (FPR)^k ≈ 3 %^5 ≈ 2.4 × 10⁻⁸` (or lower given packet loss) so each event is delivered with probability 1.

## Transit-layer Encryption

For Foward Secrecy and Post-Compromise Security against a network-surveilling attacker, all sync requests and responses are wrapped in a [Noise Protocol IKpsk2](http://www.noiseprotocol.org/noise.html#handshake-patterns) handshake that uses previously-synced, short-lived `prekey` events from each peer. The first response includes the handshake secret, followed by events wrapped in the secret.

The handshake includes `peer` and `network` packets, so that even if multiple networks (or the same network, with multiple peers) are running on the same device, the receiving client application can distinguish them. 

Handshake requests and responses are not valid if signed by a removed user or peer (see: [Removal](#removal)).

## Hole Punching

A peer can create an `intro` event that names two valid `address` events by their `id`, with an optional external port for each. (The peer sending the `intro` might know the peers' external ports when they themselves do not.) Upon receiving a valid `intro`, each peer immediately sends UDP bursts of `sync` events to the other. `intro` events should be processed as quickly as possible, and invalid `intro` events need not be buffered.

Once hole punching is successful (after the first `sync` response) peers send periodic sync events and at least one response (even if empty) as a "keep alive".

Our approach does not need to match the state of the art for hole-punching: hole-punching will never be 100% reliable and many users (e.g. those on iOS) must rely on [Optional Servers](#Optional-Servers) in any case.

# Channels

To create a channel, peers create `channel` events naming a `group-id` or `fixed-group-id`, a `channel-name`, and a `disappearing-time`. Its `event-id` is its `channel-id`.

All channel messages use the latest known `disappearing-time` (default 0 for permanent.) Backend generates `ttl`. 

Only members of the admin group can create channels; `channel` events are checked for signing by an admin. If not, we [blocking and unblocking](#blocking-and-unblocking).

Admins can issue a `channel-update` to change `channel-name` or `disappearing-time`.

Messages include `channel-id`.

## DMs

DMs (individual and group DMs) are a channel with an empty name and a `fixed-group-id`. 

To remain Slack-like, application frontends should query the list of existing DMs and guide users towards reusing existing DMs.

Unlike channels with a `group-id`, channels with a `fixed-group-id` can be deleted by all members with a `delete-channel` event.

## Channel Deletion

Deletion is possible with a `delete-channel` event naming the `channel-id`.

Only admins can delete normal channels, but any member can delete a `fixed-group` channel (DM, e.g.). 

To be sure that all messages in the channel are deleted the `delete-channel` event must last forever.

## Unread Counts and Read Receipts

Modern messengers sync unread counts across devices and many share read receipts. To achieve this, peers create `seen` events when viewing new messages, naming a `channel-id`, `viewed_at_ms` timestamp, and a `message_id`, encrypted to channel members.

`seen` events must come from members of the channel. Validation: Signer in channel; message exists with created_at_ms <= viewed_at_ms. TTL matches channel's disappearing time.

Backend computes per-user/channel: `last_seen_message_id` (from latest seen event), `last_seen_at_ms`. Unreads: Messages > last_seen_at_ms (fallback) or > last_seen_message_id.

# Blocking

Users sometimes need to block others. They do so with a `block` event naming a `user-id` encrypted to all their own peers.

`block` events are considered auth events for priority sync with `sync-auth`.

When another user is blocked, messages are invisible, and their user status displays blocked.

# Updating Events

We must update events, e.g. to edit a message, add attachments, give a `user-id` a username (or change it), add unfurl metadata to a message, update a profile image, or change a setting. To do so we create `update` events than name an `event-id`, specify an `update-type`, and include a `global-count`, along with the type-specific update content.

`global-count` increments the highest known `global-count` by 1 and the highest value "wins", with highest `event-id` as an arbitrary tiebreaker.

In general we [blocking and unblocking](#blocking-and-unblocking) for orphaned updates, though some updates (e.g. edit text) may be validated immediately if otherwise correct.

The root `event-id` must be repeated outside the [Event-layer Encryption](#Event-layer-Encryption) so that deleting the root event can delete all updates, even updates that are not known, even by peers that cannot decrypt them.

Updates must be done by a peer linked to the same `user-id` as the original event.

# Blobs

Many messages will include images, video, or too much text to fit in one event. These are held in blobs, which reference blob-parts called "slices".

For example, to add a message attachment (the `message` event has already been created) we create our slices, encrypt them with XChaCha20-Poly1305, create their ciphertext `slice` events, then create the following event:

`update|message-id|add-attachment|blob-id|blob-bytes|nonce-prefix|enc-key|root-hash`

- `message-id` is the `event-id` of the message we want to attach to 
- `blob-id` is a BLAKE2b-128 of the *complete* ciphertext stream
- `enc-key` is an XChaCha key
- `root-hash` is a BLAKE2b-256 over all ciphertext slices

Our `slice` events are:

`slice|blob-id|slice-number|nonce24|ciphertext|tag`

```
# slice encryption
slice.tag = seal(enc_key, nonce24, ciphertext)                 # XChaCha20-Poly1305

# blob identifiers
blob_id   = crypto_generichash(16, full_ciphertext)            # BLAKE2b-128  (2⁶⁴-collision)
root_hash = crypto_generichash(32, concat(slices))             # BLAKE2b-256  (2¹²⁸-collision)
```

We leave `slice-number` in plaintext so the receiver can drop the bytes straight into its sparse buffer before decryption; it is authenticated by the tag. Events are then encrypted as any other, though per-slice signatures are omitted for performance, since `root-hash` in the descriptor detects any missing or tampered slice after reassembly.

A future refinement is to include a merkle proof in each slice, so that each slice can be validated upon receipt, e.g. for DoS resilience.

Blobs should not be re-used across messages. For example, if a user forwards a blob, it should be re-created.

## Syncing Blobs

While slices are normal events and will sync eventually (see [Sync](#Sync)) we often want to prioritize and fetch slices for a wanted blob, and show download progress. We do this with a special sync event:

`sync-blob|peer|blob-id|window|bloom|limit`

```
# for each slice received:
pt = aeadOpen(enc_key, nonce24, ciphertext)           # XChaCha20-Poly1305
store(slice_number, pt)

# after last slice arrives
reassembled   = concat( slice[i] for i = 0 … last )
computed_root = crypto_generichash(32, reassembled)       # BLAKE2b-256 (2¹²⁸-collision)
assert computed_root == root_hash                         # blob integrity OK
```

Larger blobs require more windows:

```
windows(blob_bytes) = clamp(2^ceil(log2(ceil(blob_bytes / 450) / 100)), 1, 4096)  
```

Except for the new `blob-id`, `sync-blob` works the same as `sync`.

For performant file retrieval, we recommend storing blob slices sequentially, reserving space based on `blob-size`. 

# Deletion

All peers delete events upon `ttl` expiry. 

To delete a message, peer create a `delete-message` event naming the event `id`. 

`delete-message` events are typically only valid if signed by the same `user-id` that wrote the message. For messages in a `group` (but not in a `fixed-group`) admins can also delete all messages. 

Two rules: 1. Delete all existing events or updates when you get a `delete-message`. 2. Delete all new events or updates for already-received `delete-message` events.

For perfectly reliable deletion, `delete-message` events should last forever. In practice, the `ttl` can be sufficiently greater than the event it deletes so that it always outlives its deleted events.

Blob-related `slice` events may be unknown when the blob root event is deleted. Unknown blobs are deleted via "cryptographic shredding" once the originating event has been deleted, and again once their `ttl` arrives.

# Optional Servers

It is good if users can add a server: most people need a level of performance and reliability that exceeds what is *currently* possible with a peer-to-peer network, especially on iOS devices (where apps cannot run in the background.) 

For simplicity it is desirable that servers are just another peer running the same protocol and code.

We add servers with a normal invite (see: [Joining](#Joining)). The blob associated with the `invite` PAKE event can include the server's `address` event. (Peers that see the PAKE can then connect to the server, which is more reliable.)

The invite PAKE is provided to the server out of band. At this point the server can request payment, account creation, ToS and Privacy Policy approval, or CAPTCHA out of band.

If privacy from the server is not desired, we create a "member" role tag and encapsulate keys to it.

For reliability across a range of networks, peers can connect to servers over conventional transports such as WebSockets or [QUIC Streams](https://quic-go.net/docs/quic/streams/)

Only users in the admin group can add servers.

## Sync Server

A sync server will sync events without being able to decrypt them (because it is not added to the groups that all messages are sent to). This is helpful for fetching the contents of mobile push notifications reliably, for example.

For limiting data retention on the sync server, users might send with a reduced TTL. (Or, if users want permanent retention on the sync server, a "forever" TTL.)

Communities can add multiple sync servers for increased uptime, backup, censorship resistance, or other reasons.

## Push Notification Server

Communities can add an optional push notification server to deliver push notifications via Apple, Google, and others. The push server can run as the same peer as the [Sync Server](#sync-server), or a separate one.

After the Server joins the community, admins can create a `push-server` event naming its `user-id`. Other peers send events to the push server, encrypted as DMs. The event types are `push-register` to register a push token (contains an Apple/Google-provided token) and `push-mute`/`push-unmute` (containing a `group-id`) to mute/unmute notifications. These are encrypted to the service's `prekey`s. 

The Server bases its state for each peer on events with the highest count, and sends notifications to each registered peer token for all unmuted groups.

The `push-server` event can specify security settings, such as whether push notifications should include the `event-id`, the entire corresponding event, or be empty and just wake up the device.

Our sync protocol and backend must be fast enough and memory-efficient enough to run in a background notification app extension, at least over an HTTP transport.

## GDPR Compliance

In [GDPR](https://en.wikipedia.org/wiki/General_Data_Protection_Regulation) jargon the network owner is the "controller" and the optional server provider is the "processor". The controller chooses the server provider, their jurisdiction, and how long data flows through the server. 

To remain a "processor", the server operator must keep only transient buffers and IP logs strictly on the owner’s written instruction.

If the relay is outside the EEA the owner must put a Chapter V transfer mechanism in place (SCCs, adequacy, etc.).

Clients and repo docs should make it clear that a network's owners can add a new server at any time, and that it is the network owner's responsibility to post a privacy policy that names the third parties they are using and convey this to users out-of-band before they join. 

The optional Push Notification Server provider must list Apple and Google in the Data Privacy Agreement with the network owner.

# Performance

Goal: ensure this protocol is practical on mobile devices and typical network connections.

A few inefficiencies raise eyebrows. 

First is the storage of large blobs as UDP-datagram-sized packets in a relational database. For networks with 10 million events (100,000 messages and many images) performance is adequate on mobile devices. Fully p2p networks are primarily constrained by device size, and server-assisted networks benefit from adding events and blobs in large, sequential batches. Deduplication, eventual consistency, and a consistent source of truth across platforms are worth the performance sacrifice.

Second is the large amount of outgoing bloom traffic users must send to sync. The good news here is that blobs are the dominant bandwidth factor and there are much more efficient mechanisms for syncing known blobs, including very simple ones, such as [LT codes](https://en.wikipedia.org/wiki/Luby_transform_code). We are free to implement these in the future as needed.

See [Implementation Notes](#appendix-h-implementation-notes) for performance-related recommendations.  
 
## Sync Performance

Do peer states converge in a reasonable amount of time, on typical devices with typical home broadband and mobile data connections?

Key cases:
1. Alice has all messages, Bob is joining with none
2. Alice is missing a random message Bob has
3. Alice and Bob were partitioned: they have the same messages for the first half of their history, but then their messages diverge
4. Downloading images while lazy loading
5. Downloading a large file

## CPU Performance

Heavy writes are manageable on mobile devices with a WAL and batching according to tests in React Native on Android devices. There is a convenient relationship between traffic and our ability to batch: the heavier the incoming traffic, the less UX penalty we incur from holding on to 1000 unprocessed events and inserting them in a batch (we may receive thousands in a second).

For scrolling and lazy loading, queries to a local database behave as one would expect in a modern messaging app handling many messages. Standard lazy loading / progressive hydration techniques apply. Events can be indexed by createdAt, eventId, and blobId as needed. We can include blurhash in image blob events, and fetch all of an events updates when we fetch the event.

Rendering images while scrolling can be made efficient by storing all blob slices in sequence. SQLite in WAL mode is efficient at reads while handling many writes.

The CPU cost of decryption on the fly is dominated by the data retrieval cost (the former is a rounding error on the later).

---

# Appendix 

## Appendix A — Types and Layouts

##### Local-only Events

| Type | Fields | Description |
|------|--------|-------------|
| **LOCAL-ONLY-peer** | `keypair` 64 · `network_id` 16 · `created_at` 8 | Stores Ed25519 keypair for a specific network |
| **LOCAL-ONLY-network** | `group_id` 16 · `network_name` 32 · `created_at` 8 | Associates local network reference with group |

TODO - add these:

* **LOCAL-ONLY-last-noise-handshake** | `secret` | `peer` | `ttl` | (ttl is short, this is for broadcasting to peers using the last handshake secret and for knowing what network events are coming from)
* **LOCAL-ONLY-outgoing** | `noise-wrapped-event` | `due_ms` | `ttl`
(due is unix ms time, when to send it, for AIMD or staggering)
* **LOCAL-ONLY-incoming** | `noise-wrapped-event` | `received_at` | `origin_ip` | `origin_port` | `ttl`

Then the following are just the last outgoing sync events to and from each peer, used for scheduling next sync and remembering windows.

* **LOCAL-ONLY-last-sync** 
* **LOCAL-ONLY-last-sync-auth** 
* **LOCAL-ONLY-last-sync-blob** 
* **LOCAL-ONLY-last-sync-lazy** 

Note that these events might make sense in an in-memory database.

##### Blob Slice (type `0x03`)  

| Offset | Bytes | Field        |
|--------|-------|--------------|
| 0      | 1     | `version`    |
| 1      | 1     | `type`       |
| 2      | 16    | `blob_id`    |
| 18     | 4     | `slice_no`   |
| 22     | 24    | `nonce`      |
| 46     | 450   | `ciphertext` |
| 496    | 16    | `poly_tag`   |                                                                  

*Nonce is reconstructed as `nonce_prefix ∥ slice_no`; the 24-byte prefix is stored once in the original event mentioning the blob. Blob slices are not signed and are not wrapped in additional group event-layer encryption. Total size: 512 bytes exact (no pad).*

##### Common Header  

| Offset | Bytes | Field |
|--------|-------|-------|
| 0 | 1 | `version` |
| 1 | 1 | `type` |
| 2 | 4 | `count` |
| 6 | 8 | `created_at_ms` |
| 14 | 8 | `ttl_ms` |
| 22 | 32 | `peer_pk` |

*Followed by payload (bytes 50–447, 398 bytes: nonce + ct + tag if encrypted, or plaintext + zero-pad otherwise), then signature (bytes 448–511, 64 bytes, Ed25519 over bytes 0–447 plaintext form). Total: 512 bytes. Event-layer encryption: Applicable per-type notes below; if yes, reserve 40 bytes (max plaintext 358 bytes). ID computed on wire (encrypted) form for transmission, decrypted form for storage.*

| Type               | Hex  | Plaintext Layout (zero-pad remainder)                                      | Event-Layer Encryption? |
|--------------------|------|---------------------------------------------------------------------------|------------------------|
| **message**        | 0x00 | `channel_id` 16 · `text` 338                                             | Yes                    |
| **channel**        | 0x01 | `group_id` 16 · `channel_name` 32 · `disappearing_time_ms` 8 · pad (298) | Yes                    |
| **update**         | 0x02 | `event_id` 16 · `global_count` 4 · `update_code` 1 · `user_id` 16 · `body` 317 | Yes                    |
| **slice**          | 0x03 | See dedicated table above (no common header or sig)                      | No                     |
| **rekey**          | 0x04 | `original_event_id` 16 · `new_key_id` 16 · `new_ciphertext` ≤322 · pad | Yes                    |
| **delete-message** | 0x05 | `message_id` 16 · pad (338)                                              | Yes                    |
| **delete-channel** | 0x06 | `channel_id` 16 · pad (338)                                              | Yes                    |
| **sync**           | 0x07 | `window` 2 · `bloom_bits` 64 · pad (328)                 | No                     |
| **sync-auth**      | 0x08 | `window` 2 · `bloom_bits` 64 · `limit` 2 · pad (326)    | No                     |
| **sync-lazy**      | 0x09 | `cursor` 16 · `bloom_bits` 64 · `limit` 2 · `channel_id` 16 · pad (296)   | No                     |
| **sync-blob**      | 0x0A | `blob_id` 16 · `window` 2 · `bloom_bits` 64 · `limit` 2 · pad (310) | No                     |
| **intro**          | 0x0B | `address1_id` 16 · `address2_id` 16 · `nonce` 32 · pad (330)                 | No                     |
| **address**        | 0x0C | `transport` 1 · `addr` 128 · `port` 2 · pad (263)                      | No                     |
| **invite**         | 0x0D | `invite_pk` 32 · `max_join` 2 · `expiry_ms` 8 · `network_id` 16 · pad (336) | No                     |
| **user**           | 0x0E | `pake_proof` 32 · `network_id` 16 · pad (346)                          | No                     |
| **link-invite**    | 0x0F | `invite_pk` 32 · `max_join` 2 · `expiry_ms` 8 · `user_id` 16 · `network_id` 16 · pad (320) | No                     |
| **link**           | 0x10 | `pake_proof` 32 · `user_id` 16 · `network_id` 16 · pad (330)           | No                     |
| **remove-peer**  | 0x11 | `peer_id` 32 · pad (362)                                             | No                     |
| **remove-user**    | 0x12 | `user_id` 16 · pad (378)                                               | No                     |
| **block**          | 0x13 | `blocked_user_id` 16 · `global_count` 4 · pad (334)                    | Yes (self-only)        |
| **group**          | 0x14 | `user_id` 16 · `group_name` 32 · pad (306)                              | Yes                    |
| **update-group-name** | 0x15| `group_id` 16 · `new_name` 32 · pad (306)                              | Yes                    |
| **fixed-group**    | 0x16 | `num_members` 1 · `user_ids` (16 each, ≤20, sorted) · pad (≤353)       | Yes                    |
| **grant**          | 0x17 | `group_id` 16 · `user_id` 16 · pad (322)                               | Yes                    |
| **key**            | 0x18 | `type_inner` 1 · `peer_pk` 32 · `count` 4 · `created_ms` 8 · `ttl_ms` 8 · `tagId` 16 · `prekey_id` 16 · `sealed_key` 80 · pad (229) | No                     |
| **prekey**         | 0x19 | `group_id` 16 · `channel_id` 16 · `prekey_pub` 32 · `eol_ms` 8 · pad (322)               | No                     |
| **push-server**    | 0x1A | `user_id` 16 · `security_settings` 4 · `pad`  (338)	                                              | Yes                    |
| **push-register**  | 0x1B | `token` 128 · `ttl_ms` 8 · pad (218)                                   | Yes                    |
| **push-mute**      | 0x1C | `channel_id` 16 · pad (338)                             | Yes                    |
| **push-unmute**    | 0x1D | `channel_id` 16 · pad (338)                             | Yes                    |
| **mute-channel**   | 0x1E | `channel_id` 16 · `mute_flag` 1 · pad (337)                            | Yes (self-only)        |
| **channel-update** | 0x1F | `channel_id` 16 · `new_channel_name` 32 · `new_disappearing_time_ms` 8 · `global_count` 4 · pad (294) | Yes                    |
| **unblock**        | 0x20 | `blocked_user_id` 16 · `global_count` 4 · pad (334)                    | Yes (self-only)        |
| **seen**           | 0x21 | `channel_id` 16 · `viewed_at_ms` 8 · `message_id` 16 · pad (314)       | Yes                    |

**Note**: Reserved codes (≥0x22) for future events; plaintext payload MUST be zero. Encrypted types pad to 354 bytes (394 - 40 for encryption); non-encrypted to 394 bytes.

`security_settings` in **push-register** are: 
* 0 - send empty notification for silent wake‑up
* 1 - include event_id in payload
* 2 	include full event (ciphertext) in payload
* 3‑31 	reserved

## Appendix B — Update Codes

This table applies to the **update** plaintext payload block: `event_id` 16 | `global_count` 4 | `update_code` 1 | `body` 321. Body layouts reserve space for encryption (max body 321 in plaintext).

| Name / Purpose              | Hex  | 321-byte **Body** Layout (fixed-length, zero-pad remainder)                               |
|-----------------------------|------|-------------------------------------------------------------------------------------------|
| **edit-message-text**       | 0x00 | `utf-8 text` ≤321 B                                                                       |
| **add-attachment**          | 0x01 | `blob_id` 16 · `blob_bytes` 8 · `nonce_prefix` 4 · `enc_key` 32 · `root_hash` 32 · pad (229) |
| **add-unfurl** (Open Graph) | 0x02 | `url_hash` 16 · `thumb_blob_id` 16 · `og_title` 64 · `og_description` 128 · `blob_id` 16 · `blob_bytes` 8 · `nonce_prefix` 4 · `enc_key` 32 · `root_hash` 32 · pad (5)    |
| **add-reaction**            | 0x03 | `emoji_utf32` 4 · `user_group_id` 16 · pad (301)                                          |
| **remove-reaction**         | 0x04 | `emoji_utf32` 4 · `user_group_id` 16 · pad (301)                                          |
| **update-username**         | 0x05 | `utf-8 new name` ≤321 B (targets a `user` event’s `id`)                                   |
| **update-profile-image**    | 0x06 | `blob_id` 16 · `blob_bytes` 8 · `nonce_prefix` 4 · `enc_key` 32 · `root_hash` 32 · pad (229)                                                                  |
| **add-prekey**              | 0x07 | `prekey_pub` 32 · `eol_ms` 8 · pad (281)                                                  |
| *reserved*                  | ≥0x08| zero-filled until defined                                                                 

Events **update-username** and **update-profile-image** name the `user` event-id for the user they are updating.

## Appendix C — Joining PAKE

We use SPAKE2-Ed25519 to let peers join networks without revealing anything to a network adversary or an attacker who intercepts an expired PAKE. 

Group: Ed25519, order ℓ, base g.
H2C = hash-to-curve (trial hash until valid point).
KDF = BLAKE2b.

```
# constants per network
M = H2C("quiet-M|" ∥ nid)          # hash_to_curve
N = H2C("quiet-N|" ∥ nid)

# invite code → scalar
pw_bytes = BLAKE2b("quiet-invite" ∥ C ∥ nid, 64)
pw = crypto_core_ed25519_scalar_reduce(pw_bytes)

# Alice side
x_bytes = random 64 bytes
x  = crypto_core_ed25519_scalar_reduce(x_bytes)
X  = crypto_scalarmult_ed25519_base_noclamp(x) + crypto_scalarmult_ed25519_noclamp(pw, M)

# Bob side produces Y analogously, then both compute
K  = crypto_scalarmult_ed25519_noclamp(x, Y − crypto_scalarmult_ed25519_noclamp(pw, N))
sk = BLAKE2b("quiet-pake" ∥ K, 32)
```

Libsodium calls:

```
// hash to curve
counter = 0
while (true) {
    candidate = crypto_hash_sha512("quiet-M|" ∥ nid ∥ counter)[:32]
    if (crypto_core_ed25519_is_valid_point(candidate))
        return candidate
    counter++
}

// derive X, Y
    x_bytes = randombytes(64)
    x       = crypto_core_ed25519_scalar_reduce(x_bytes)
    gx      = crypto_scalarmult_ed25519_base_noclamp(x)
    Mpw     = crypto_scalarmult_ed25519_noclamp(pw, M)
    X       = crypto_core_ed25519_add(gx, Mpw)

// shared secret
    Npw     = crypto_scalarmult_ed25519_noclamp(pw, N)
    Y_sub   = crypto_core_ed25519_sub(Y, Npw)
    K       = crypto_scalarmult_ed25519_noclamp(x, Y_sub)
    sk      = crypto_generichash(32, "quiet-pake" ∥ K)

/* wipe */
sodium_memzero(x, 32);
sodium_memzero(K, 32);
```

The PAKE payload can be a blob including any information the inviter peer wants to provide, including KEM events necessary for viewing current or previous messages, or group grants (see [Event-Layer Encryption](#event-layer-encryption) and [Groups and Invites](#groups-and-invites)). 

#### Joining PAKE and Prekeys

Prekeys for a given PAKE password (`invite` event) are created as follows:

```
pw = random 32-byte invite secret  // e.g., crypto_randombytes(pw, 32)

NUM_PREKEYS = 100

master_key = crypto_generichash(32, pw ∥ "quiet-invite-prekeys")

for i from 0 to NUM_PREKEYS-1:
    ctx = "prekey-" + i as little-endian uint32  // 11 bytes total
    
    priv_bytes = crypto_generichash(64, master_key ∥ ctx)
    priv_i = crypto_core_ed25519_scalar_reduce(priv_bytes)
    
    pub_i = crypto_scalarmult_ed25519_base_noclamp(priv_i)
    
    sodium_memzero(priv_i, 32);      /* wipe loop scalar */
}
sodium_memzero(master_key, 32);      /* wipe master key */
```

After creating the keys, the creator creates signed `add-prekey` update events for each and discards the private keys. Invitees re-derive them on join. 

## Appendix D — Auth-Related Events

Here we list all events that are auth-related and can be prioritied with `sync-auth`: 

- **block**
- **unblock**
- **delete-message**
- **delete-channel**
- **key**
- **prekey**
- **remove-user**
- **remove-peer**
- **group**
- **grant**
- **fixed-group**
- **invite**
- **link-invite**
- **user**
- **link**
- **channel**
- **seen**

## Appendix E — API Documentation

This appendix describes a RESTful API for frontend applications to interact with the protocol backend (e.g., over a local SQLite database). The API is per-network, with each network exposing a unique endpoint (e.g., `https://localhost:8080/networks/{network_id}/`). Authentication uses a pre-shared key (PSK) provided via IPC, with all requests over TLS.

### General Principles
- Aggregate data backend-side (e.g., updates into messages, seen events into unreads/seen_by) for "dumb frontend"—no client-side reconstruction.
- Responses: Denormalized, ready-to-render. Reference blobs by ID (fetch separately via GET /blobs/{blob_id} for perf). Add ETag for efficient polling.
- Authentication: PSK via IPC, TLS.

### Error Responses
HTTP codes (400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found). Body: `{"error": "description", "details": {}}`. 
201 Created is used for all resource creation endpoints.

### Resources

#### Networks

- **GET /networks**  
  List joined networks. Query: `?cursor=hex&limit=50`.  
  Response: `{"items": [{"network_id": "hex", "name": "string", "created_at_ms": int}], "next_cursor": "hex", "has_more": bool}`

- **POST /networks**  
  Create network.  
  Request: `{"name": "string"}`  
  Response: 201 Created, `{"network_id": "hex"}`  
  Headers: `Location: /networks/{network_id}`  
  (Generates `group` event for admins.)

- **POST /networks/join**  
  Join via invite.  
  Request: `{"encoded_data": "base64"}` (parses to secret/network_id/peer) or fallback `{"invite_secret": "bytes", "network_id": "hex", "address_event": {...}}`  
  Response: `{"success": true}`  
  (Generates `user` and `address` events; encrypted as per updates.)

- **DELETE /networks/{network_id}**  
  Leave network (self-only, non-admins).  
  Response: `{"success": true}`  
  (Generates `remove-user` for self; purges local data.)

#### Users
- **GET /networks/{network_id}/users**  
  List users. Query: `?group_id=hex&cursor=hex&limit=50`.  
  Response: `{"items": [{"user_id": "hex", "username": "string", "peer_ids": ["hex"], "created_at_ms": int}], "next_cursor": "hex", "has_more": bool}`

- **GET /networks/{network_id}/users/{user_id}**  
  Get user.  
  Response: Single user object.

- **PATCH /networks/{network_id}/users/{user_id}**  
  Update profile (self). Request: `{"username": "string", "avatar_data": "base64"}` (creates blob).  
  Response: Updated user.  
  403 if not self or linked peer.

- **DELETE /networks/{network_id}/users/{user_id}**  
  Remove user (self/admin).  
  Response: `{"success": true}`  
  403 if not self/admin.  
  (Generates `remove-user`.)

- **POST /networks/{network_id}/users/{user_id}/link-invites**  
  Same as above, but for linking. Response includes secret/encoded_data. 403 if not primary/linked.

- **POST /networks/{network_id}/peers/link**  
  Claim link invite (on new peer). Request: `{"encoded_data": "base64"}`.  
  Response: 201 Created, `{"peer_id": "hex"}`  
  (Generates `link` event.)

- **DELETE /networks/{network_id}/users/{user_id}/peers/{peer_id}**  
  Remove peer.  
  Response: `{"success": true}`  
  403 if not self/admin.  
  (Generates `remove-peer`.)

- **POST /networks/{network_id}/blocks**  
  Block user. Request: `{"user_id": "hex"}`.  
  Response: 201 Created, `{"success": true}`  
  Note: Blocks are auth-related and prioritize via sync-auth.  
  (Generates `block`.)

- **DELETE /networks/{network_id}/blocks/{user_id}**  
  Unblock.  
  Response: `{"success": true}`  
  (Generates `unblock`.)

#### Groups
- **GET /networks/{network_id}/groups**  
  List groups. Query: `?cursor=hex&limit=50`.  
  Response: `{"items": [{"group_id": "hex", "members": ["user_id"], "is_fixed": bool, "name": "string", "created_at_ms": int}], "next_cursor": "hex", "has_more": bool}`

- **GET /networks/{network_id}/groups/{group_id}/members**  
  List members.  
  Response: `[{"user_id": "hex", "joined_at_ms": int}]` (From `grant` or fixed members.)

- **POST /networks/{network_id}/groups**  
  Create group. Request uses oneOf:  
  Dynamic: `{"initial_user_id": "hex", "name": "string"}`  
  Fixed: `{"fixed_members": ["user_id"]}` (1-20 members, backend sorts)  
  Response: 201 Created, `{"group_id": "hex"}`  
  400 if both types provided.  
  (Generates `group` or `fixed-group`.)

- **POST /networks/{network_id}/groups/{group_id}/grants**  
  Add member (admin). Request: `{"user_id": "hex"}`.  
  Response: 201 Created, `{"success": true}`  
  403 if not admin.  
  (Generates `grant`.)

- **PATCH /networks/{network_id}/groups/{group_id}**  
  Update (admin, non-fixed). Request: `{"name": "string"}`.  
  Response: Updated group.  
  403 if not admin or is fixed group.  
  (Generates `group-name` event.)

#### Channels
- **GET /networks/{network_id}/channels**  
  List. Query: `?group_id=hex&cursor=hex&limit=50`.  
  Response: `{"items": [{"channel_id": "hex", "group_id": "hex", "channel_name": "string", "disappearing_time_ms": int, "message_count": int, "created_at_ms": int}], "next_cursor": "hex", "has_more": bool}`

- **POST /networks/{network_id}/channels**  
  Create (admin for normal; any for fixed/DMs). Request: `{"group_id": "hex", "channel_name": "string", "disappearing_time_ms": int}`.  
  Response: 201 Created, `{"channel_id": "hex"}`  
  403 if not admin (for normal groups).  
  (Generates `channel`.)

- **GET /networks/{network_id}/channels/{channel_id}**  
  Get details.  
  Response: Single channel object.

- **PATCH /networks/{network_id}/channels/{channel_id}**  
  Update (admin/any for fixed). Request: `{"channel_name": "string", "disappearing_time_ms": int}` (partial).  
  Response: Updated channel.  
  403 if not admin (for normal groups).  
  (Generates `channel-update`.)

- **DELETE /networks/{network_id}/channels/{channel_id}**  
  Delete.  
  Response: `{"success": true}`  
  403 if non-member attempting fixed-group delete.  
  (Generates `delete-channel`.)

- **POST /networks/{network_id}/channels/{channel_id}/mute**  
  Mute (self).  
  Response: `{"success": true}`  
  (Generates `mute-channel`.)

- **POST /networks/{network_id}/channels/{channel_id}/unmute**  
  Unmute (self).  
  Response: `{"success": true}`  
  (Generates `unmute-channel`.)

#### Messages
- **GET /networks/{network_id}/channels/{channel_id}/messages**  
  List (paginated). Query: `?cursor=hex&limit=50&since_ms=int`.  
  Query: `?cursor=hex&limit=50&since_ms=int`.  
  Response: `{"items": [{"message_id": "hex", "user_id": "hex", "text": "string" (latest from edits), "created_at_ms": int, "edited_at_ms": int or null, "attachments": [{"blob_id": "hex", "blob_bytes": int, "filename": "string" or null, "blurhash": "string" or null, "mime_type": "string" or null}], "unfurls": [{"url": "string", "og_title": "string", "og_description": "string", "og_image_blob_id": "hex" or null, "og_site_name": "string" or null, "og_url": "string" or null}], "reactions": [{"emoji": "string", "count": int, "user_ids": ["hex"]}], "is_unread": bool (true if > user's last_seen_at_ms), "seen_by": [{"user_id": "hex", "viewed_at_ms": int}] (users with last_seen >= this message; optional, config-enabled for read receipts)}], "next_cursor": "hex", "has_more": bool}`.  
  Aggregation: Collect unique attachments/unfurls; net reactions; ignore buffered/invalid updates. Exclude deleted messages (or return tombstone: {"message_id": "hex", "deleted": true}).

- **POST /networks/{network_id}/channels/{channel_id}/messages**  
  Send. Request: `{"text": "string", "attachments": [{"data": "base64", "filename": "string"}], "unfurls": [{"url": "string", "data": "base64"}]}`.  
  Response: 201 Created, `{"message_id": "hex"}`  
  (Generates `message`, optional `update`.)

- **GET /networks/{network_id}/messages/{message_id}**  
  Get.  
  Response: Single message object.

- **PATCH /networks/{network_id}/messages/{message_id}**  
  Update (creator). Request: `{"text": "string", "add_attachment": {"data": "base64"}, "add_unfurl": {"url": "string", "data": "base64"}, "add_reaction": "👍"}` (partial).  
  Response: Updated message.  
  403 if not creator.

- **DELETE /networks/{network_id}/messages/{message_id}**  
  Delete (author/admin).  
  Response: `{"success": true}`  
  403 if not author/admin.  
  (Generates `delete-message`.)

- **DELETE /networks/{network_id}/messages/{message_id}/reactions/{emoji}**  
  Remove reaction.  
  Response: `{"success": true}`

#### Blobs
- **GET /networks/{network_id}/blobs/{blob_id}**  
  Download.  
  Response: Binary (streamed).

- **GET /networks/{network_id}/blobs/{blob_id}/status**  
  Progress.  
  Response: `{"status": "downloading|complete|failed", "progress": 0.75, "bytes_downloaded": int, "bytes_total": int}`

#### Invites
- **POST /networks/{network_id}/invites**  
  Create (admin only). Request: `{"expiry_ms": int, "max_joiners": int}`.  
  Response: 201 Created, `{"invite_secret": "bytes", "invite_public_key": "bytes"}`  
  403 if not admin.  
  (Generates `invite`; encrypted to network group.)

#### Sync
- **GET /networks/{network_id}/sync/status**  
  Status.  
  Response: `{"peers_connected": int, "events_pending": int}`

- **POST /networks/{network_id}/sync-requests**  
  Force sync. Request: `{"type": "full|auth|lazy|blob"}` (optional).  
  Response: 201 Created, `{"success": true}`

- **POST /networks/{network_id}/sync-blob**  
  Sync specific blob. Request: `{"blob_id": "hex", "window": int, "bloom": "base64", "limit": int}`.  
  Response: `{"success": true}`

#### Debug (Dev/testing only; MUST NOT be in prod builds)
- **POST /debug/networks/{network_id}/simulate**  
  Simulate. Request: `{"initial_events": [], "new_events": []}`.  
  Response: `{"result_state": [], "emitted": []}`

- **POST /debug/networks/{network_id}/prekeys**  
  Create. Request: `{"count": int}`.  
  Response: 201 Created, `{"prekey_ids": ["hex"]}`

- **POST /debug/networks/{network_id}/rekey**  
  Rekey/purge. Request: `{"event_ids": ["hex"]}`.  
  Response: `{"rekeyed_count": int, "purged_keys": int}`

- **GET /debug/networks/{network_id}/blocked**  
  Blocked events.  
  Response: `[{"event_id": "hex", "type": "string", "status": "blocked"}]`

- **POST /debug/networks/{network_id}/intro**  
  Simulate intro. Request: `{"peer1_id": "hex", "peer2_id": "hex"}`.  
  Response: `{"emitted": [{"type": "intro", ...}]}`  
  (Generates `intro`.)

- **POST /debug/networks/{network_id}/address**  
  Emit address. Request: `{"transport": 1, "addr": "string", "port": int}`.  
  Response: 201 Created, `{"address_id": "hex"}`

- **POST /debug/networks/{network_id}/index**  
  Create index. Request: `{"query": "string"}`.  
  Response: 201 Created, `{"index_id": "hex"}`  
  (Generates `index`; encrypted.)

#### Search
- **GET /networks/{network_id}/search**  
  Search messages. Query: `?query=string&channel_id=hex&limit=50`.  
  Response: `{"items": [message objects], "next_cursor": "hex", "has_more": bool}`

#### Servers
- **POST /networks/{network_id}/servers/sync** (admin only)  
  Add sync server. Request: `{"invite_secret": "bytes"}`.  
  Response: 201 Created, `{"server_user_id": "hex"}`  
  403 if not admin.  
  (Joins via PAKE; blinded sync.)

- **POST /networks/{network_id}/servers/push** (admin only)  
  Add push server. Request: `{"user_id": "hex", "security_settings": {"include_event_id": bool}}`.  
  Response: 201 Created, `{"success": true}`  
  403 if not admin.  
  (Generates `push-server`.)

- **GET /networks/{network_id}/servers**  
  List.  
  Response: `[{"type": "sync|push", "user_id": "hex", "status": "active|inactive"}]`

- **DELETE /networks/{network_id}/servers/{user_id}** (admin only)  
  Remove.  
  Response: `{"success": true}`  
  403 if not admin.  
  (Generates `remove-user`.)

#### Push Notifications
- **POST /networks/{network_id}/push/register**  
  Register. Request: `{"token": "string"}`.  
  Response: 201 Created, `{"success": true}`  
  (Generates `push-register`; encrypted to server.)

- **POST /networks/{network_id}/push/mute**  
  Request: `{"channel_id": "hex"}`.  
  Response: `{"success": true}`  
  (Generates updated events.)

- **POST /networks/{network_id}/push/unmute**  
  Request: `{"channel_id": "hex"}`.  
  Response: `{"success": true}`  
  (Generates updated events.)

## Appendix F — Threat Model

### Usage Scenario

A team uses Quiet as a Slack replacement for team chat. The team has an existing secure communications channel for sending and receiving initial invitations (e.g. a Signal group). Every team member has an authentic, non-malicious version of the Quiet app, and all team members use full-disk encryption with user-controlled keys and a strong password.

### Definitions

* DELETED means any data that all MEMBER clients have reported deleted, and that users have not archived using other means, for example by taking a screenshot of chats, by inadvertently backing up app data with cloud backup tools, or by tampering with the app to block deletion.
* PURGED means all DELETED messages where key material has also been purged.
* REMOVED means any device or team member that all clients have reported is removed.

### Adversaries

* ADMIN is the first MEMBER, or any MEMBER who has been made ADMIN by another ADMIN.
* MEMBER is a user who has been invited to a group by a non-malicious ADMIN and is known to all other MEMBERs, with no other capabilities.
* NON-MEMBER is a user who has never been invited to a group, or a user who was REMOVED by an ADMIN, with no other capabilities.
* SYNC SERVER is the operator of a community’s [Sync Server](#sync-server), its cloud service provider, or an attacker who has gained privileged access to it.
* PUSH SERVER is an optional [Push Notification Server](#push-notification-server) service for delivering mobile push notifications.
*  PROVIDER is a push notification service belonging to Apple or Google (e.g., APNS or FCM). 
* DRAGNET can intercept a team’s network traffic, archive it for later decryption, and perform [traffic analysis](https://en.wikipedia.org/wiki/Traffic_analysis#In_computer_security) attacks at the limit of what is theoretically possible. 
* MALWARE can access keys or messages on the device of a member VICTIM, but has no other capabilities (such as recovering deleted data from a device.)
* MALWARE + DRAGNET can do everything MALWARE and DRAGNET can do, but has no other capabilities.
* NETWORK ACTIVE ATTACKER can both monitor and actively attack the network (for example by blocking access to the network entirely for everyone or certain users, blocking specific pieces of data from reaching their destination, or altering data in transit) but has no other capabilities.

*All adversaries assumed pre-quantum until [post-quantum](#notes-on-post-quantum) measures are implemented.*

### Security Invariants

ADMIN cannot:

* Read messages from private chats or direct messages that did not include them, or cause these messages to be DELETED.
* Read DELETED messages.
* Cause the contents of messages sent by other MEMBERS to appear incorrectly in any way.
* Cause any message to appear as if it was sent twice when it was only sent once.
* Crash the app or device of MEMBERS.
* Learn the private keys of any MEMBER.

MEMBER cannot:

* Do anything ADMIN cannot do.
* Send messages that appear to be from any other MEMBER, or cause the sender of any message to appear incorrectly in any way.
* Add or remove MEMBERS, or make anyone else an ADMIN.

MALWARE cannot:

* Do anything VICTIM cannot do. (VICTIM can be either MEMBER or ADMIN.)

MALWARE + SYNC SERVER cannot:

* Access any private chats or direct messages that did not include VICTIM.
* Access any PURGED messages.
* Cause the contents of messages sent by other MEMBERS to appear incorrectly in any way.
* Cause any message to appear as if it was sent twice when it was only sent once.
* Crash the app or device of other MEMBERS.
* Learn the private keys of any other MEMBER.

NETWORK ACTIVE ATTACKER cannot:

* Read any group messages.
* Send messages that appear to be from any MEMBER.
* Send messages to any MEMBER.
* Learn the usernames of MEMBERS.
* Crash the app or device of MEMBERS.
* Learn the private keys of any MEMBER.
* Alter the contents, sender, or timestamp of any message a MEMBER sees, in any way, including by causing any message to appear as if it was sent twice when it was only sent once.

SYNC SERVER cannot:

* Do anything NETWORK ACTIVE ATTACKER cannot do.

PUSH SERVER and PUSH PROVIDER cannot:

* Do anything SYNC SERVER cannot do.

DRAGNET cannot:

* Do anything NETWORK ACTIVE ATTACKER cannot do. 

NON-MEMBER cannot:

* Do anything DRAGNET cannot do.
* Do anything ADMIN cannot do. 
* Determine when any MEMBER is online/active.
* Degrade app functionality for any MEMBER.

## Known Weaknesses

MEMBER can:

* Degrade app functionality for any MEMBER, e.g. by spamming, or failing to relay messages to or from a MEMBER.
* Prevent the *ADMIN* from removing them.
* Prevent any message (or all messages) from being DELETED or PURGED without the knowledge of other users, e.g. by screenshotting it, or by archiving app data.
* Provide an inaccurate record of their own messages to other MEMBERS, for example by altering message contents or timestamps. [2]
* Learn the IP address of other MEMBERS.
* Learn which MEMBERS are communicating to each other, and when, in private chats and direct messages that do not include them.
* Learn if a MEMBER in one group is also a MEMBER of another group.
* Determine when any MEMBER is online/active.
* Degrade server performance or arbitrarily increase operational costs, e.g. through spam or DDoS attacks.
* Send a message that appears to be from another MEMBER to users that do not know that MEMBER has joined.
* Cause a "duplicate username" warning to appear by changing their username to be identical to that of another MEMBER.

ADMIN can:

* Do anything a MEMBER can do.
* Add and remove MEMBERS.
* Potentially re-add themselves before all clients know of the removal.

DRAGNET can:

* Learn who is using the app.
* Learn the IP address of any MEMBER.
* Learn which groups any MEMBER belongs to.
* Learn which MEMBERS are communicating to each other, and when.
* Determine when any MEMBER is online/active.

MALWARE can:

* Do anything a MEMBER can do, as VICTIM.
* Do anything *ADMIN* can do, if VICTIM is *ADMIN*.
* Send messages as VICTIM.
* Read all non-DELETED messages readable by VICTIM, including all future messages until VICTIM is REMOVED.
* Learn the IP address of VICTIM. 

MALWARE + SYNC SERVER can:

* Do anything MALWARE or DRAGNET can do.
* Read all non-PURGED messages once readable by VICTIM.

NETWORK ACTIVE ATTACKER can:

* Do anything DRAGNET can do.
* Degrade app functionality for any user.

SYNC SERVER can:

* Do anything DRAGNET can do.
* Archive messages (including DELETED messages) for later decryption by MALWARE, until they are PURGED.
* Degrade server-based functionality for any user (including iOS push notifications and messaging between iOS devices) but not peer-to-peer functionality.

PUSH SERVER and PUSH PROVIDER can:

* Learn device IDs to IP address relationship of any mobile user who enables push notifications.
* Degrade push notification service for any user.
* Degrade server-based functionality for any user, except as related to mobile push notifications.

## Appendix G — Event Validation

Event validation is core to the protocol's security and function.

### Decision Tree

```
BEGIN DB TRANSACTION
│
├─ 1. Transit‑layer unwrap (Noise)
│     ├─ Extract key‑hint from handshake plaintext
│     ├─ Locate decrypt key → infer (network_id, peer_id)
│     │     ├─ Key missing             → status = BLOCKED; index(refs); ROLLBACK
│     │     └─ Key found               → continue
│     ├─ Decrypt frame
│     │     ├─ MAC/length fail         → INVALID; ROLLBACK
│     │     └─ Success                 → continue
│     └─ Early removal checks
│           ├─ peer_id removed         → DROP; COMMIT
│           └─ user_id removed (via peer metadata) → DROP; COMMIT
│
├─ 2. Parse event envelope
│     ├─ Unsupported version           → INVALID; ROLLBACK
│     ├─ Duplicate id                  → IGNORE; COMMIT
│     └─ Continue
│
├─ 3. Dependency & key availability
│     ├─ Any dep/key missing           → status = BLOCKED; index(refs); ROLLBACK
│     └─ All available                 → continue
│
├─ 4. Signature & content checks
│     ├─ Signed by removed peer        → INVALID; ROLLBACK
│     ├─ Bad signature                 → INVALID; ROLLBACK
│     ├─ Schema / business‑rule fail   → INVALID; ROLLBACK
│     └─ Pass                          → continue
│
├─ 5. Side‑effects
│     ├─ Apply state mutations
│     ├─ For `delete‑user` etc. purge related rows/events
│     └─ Capture refs just satisfied
│
├─ 6. Re‑queue blocked events
│     └─ For every event whose BLOCKED refs intersect the refs just satisfied,
│        set state = INCOMING  (no full ref‑set check)
│
└─ 7. Mark this event VALID; COMMIT

```

## Appendix H: Implementation Notes

### Storing Events

The protocol expects that all events and metadata be stored in a modern relational database, e.g. SQLite.

#### Deletion

All deletion should use the secure delete features of the local data store (e.g. PRAGMA secure delete in SQLite, and WAL reset).

### API

To be able to use standard frontend patterns on desktop and mobile we use a relational database storing events (e.g. SQLite) to provide a REST API.

#### API Authentication

The frontend receives a PSK through some other channel (IPC) and uses TLS 

#### Frontend / backend sync

To minimize "drift" between frontend and backend state, we tear down and re-poll the backend as much as possible. When necessary we can trigger polling on the arrival of certain events, e.g. new messages in the current channel.

#### Loops

The API provides a `tick` endpoint that takes a`time_ms` parameter and triggers all event processing, creation, and deletion. 

For events that are constructed or processed periodically, such as `sync`, `prekey`, and `rekey`, we use [Local-only Events](#local-only-events-1) to track the last time these events were executed and determine whether they should be executed again in this `tick`. For any events that are more efficient to process in large batches (like `blob`s) we can use the same approach: track the last time they were performed and do a big batch.

In production use, `tick` can be triggered as often as is practical, with the current time. We can also limit the number of events processed in a typical `tick`. 

In [Deterministic Testing and Simulation](#deterministic-testing--simulation), `tick` can pass the simulation time, stepping through time as needed.

### Local-only Events

It is convenient for testing if local-only data such as `peer-id` private keys to be stored as events too.

Data for local-only use is stored in events prefixed with `LOCAL-ONLY-`. `LOCAL-ONLY-` events MUST never be shared, and `LOCAL-ONLY-` events from external sources MUST never be validated.

These events are not synced so they can be deleted conventionally. Secure delete should be used for keys.

#### Peer Keys

When joining or creating a network, clients first create a `LOCAL-ONLY-peer` event containing her keypair. This event is specific to the application, the device, and the network. If a client joins 5 networks in 2 different applications on her phone, it will have 10 `LOCAL-ONLY-peer` events.

#### Prekeys

When creating a `prekey` event, clients create a `LOCAL-ONLY-prekey-secret` event containing the keypair. Prekeys for purged messages are purged for [forward secrecy](#forward-secrecy). 

#### Network Creation

When creating the `group` event for the network, clients create a `LOCAL-ONLY-network` event naming the `group-id`.

#### Sync

The sync process requires some minimal state, such as recently seen peers and the last-used window. 

##### Last-sent

Recent events can store this with `LOCAL-ONLY-latest-sync` events that including the entire last-sent sync event for a given sync type and `peer-id`. We delete each when a new one for the `peer-id` is created.

##### Last-received

##### Outgoing

We keep `LOCAL-ONLY-outbox` events which contain ready-to-send (fully transit and event-layer encrypted) events with an `address` event and `due` field with the wall-clock time when an outgoing event can be sent.

In the future, `address` can specify different transport types. 

Each transport has a loop that queries `LOCAL-ONLY-outbox` events for `due` events for that transport and sends out bursts. 

##### Incoming

`LOCAL-ONLY-inbox` events include `origin_ip`, `origin_port`, and `received_at_ms` fields. These are added by our network interface.

#### Blobs

When the API requests a `blob`, we remember that it is desired with a `LOCAL-ONLY-blob-wanted` event with a `ttl`. 

The `ttl` here functions as a timeout and can be set depending on the type of blob: a large file might have a 0 (forever) `ttl` until complete, at which point it is deleted. A `blob` for an image loaded while scrolling might have a very near/short `ttl`, under the assumption that the user might soon scroll on to other images and prefer to prioritize those. 

##### Transit-layer Encryption 

Transsit-layer Encryption requires some minimal state. 

##### Window Strategy

Bloom filters have false positive rates, so some events could fail to sync forever. For this reason we limit the bloom filter to a window, and decrease our window size as the number of events grows.

We begin with 4096 windows, useful for up to ~1.8 million events.

`window_id = BLAKE2b-256(event_id) >> (256-w)`   // high-order w bits
`W = 2ʷ windows` // default w = 12, W = 4096

To prevent an attacker from maliciously filling bloom windows with false positives, for each window the requester derives a 16‑byte salt as BLAKE2b-128( peer_pk ∥ window_id ) and feeds it into the k = 5 Bloom hashes. Responders MUST use the supplied salt when checking membership.

We walk windows in a pseudo-random permutation (PRP), remembering the last window.

When total events seen > `W * 450`, increase `w` by 1. This makes windows smaller to keep a low false-positive rate. 

For blobs, number of windows W = max(1, ceil(total_slices / 100)) up to 4096 (w=12), where total_slices = ceil(blob_bytes / 450), ensuring ~50-100 slices per window for low FPR.

##### Congestion control

When using a transport without congestion control, such as UDP, the requester avoids congestion collapse by adjusting the rate of `sync` events using Additive Increase Multiplicative Decrease (AIMD) when incoming packets drop below an Exponential Moving Average (EMA). EMA formula: 

```
# Initial values
rate = 10  # pkts/sec
ema = 0    # initial drop rate
alpha = 0.125  # EMA smoothing

while syncing:
    send_at_rate(rate)
    drop_rate = calculate_current_drop_rate()  # e.g., lost_pkts / sent_pkts
    ema = alpha * drop_rate + (1 - alpha) * ema  # update EMA
    if drop_rate > ema:  # Congestion detected
        rate = max(1, rate * 0.5)  # Multiplicative decrease
    else:
        rate += 1  # Additive increase
    sleep(1 / rate)  # Adjust send interval
```

When sending events via QUIC/HTTP (using an [Optional Server](#Optional Servers) e.g.) we can skip this.

### Broadcast

When a peer creates new events it is most efficient to broadcast them immediately to as many other peers as practical. These can be wrapped in the latest [Transit-layer Encryption](#transit-layer-encryption) secrets used with each peer. To avoid an explosion of broadcast events we use `lazy-sync` for spreading beyond the first hop.

### Multiple networks

As in Slack and Discord, users may belong to multiple networks for different communities or work contexts. Networks are distinguished by the keys used at the level of [Transit-Layer Encryption](#transit-layer-encryption). Each network provides the frontend with a unique API endpoint, and endpoints for creating, joining, or leaving networks.

### Search and indexing

For typical communities, text will use only 3-10% of the storage of a community, and disappearing messages will be enabled, so it will be practical to store, index, and search messages locally within a few minutes or hours, even while offloading most storage (for images, videos, e.g.) to an optional server.

When communities are too large to sync even text locally, peers can create `index` events describing full-text search, using some commutative approach to indexing such as Prolly Trees.

### Deterministic Testing and Simulation

#### One-round Deterministic Testing

We can write basic deterministic tests for any common scenario as:

```
pre_tick = {incoming[], validated: {}, blocked: {}, api-calls: []}

post_tick = {incoming[], validated: {}, blocked: {}, api-responses[], outgoing[]}

expect.client(pre_tick).tick(time_ms).to.Equal(post_tick)
```

This uses the same `tick` feature of the API triggered periodically in production, in the same way.

Note that because our client can be multiple peers on multiple networks, each `pre-tick` and `post-tick` state can include many peers running on the same client, perhaps participating in the same network (as different users or devices) or on multiple networks. 

It is for this reason that `api-calls[]` is an array: since API calls specify the peer and network, it can include one API call for each peer. (TODO: this implies a change in the API structure where the lowest level must be `peer-id`, not `network`)

Finally, in packets in `incoming[]` can have an `arrives_at_ms` field, so that we can model packets that have not arrived yet by skipping over them. (Incoming cannot be processed until the `t_ms` reaches `arrives_at_ms`. If they are processed later, this is adequate for most simulation purposes, and we can adjust the `t_ms` granularity to match real-world clients.)

##### Seeding Non-deterministic Events

Crypto ops (e.g., keygen, hashes) and randomness (e.g., bloom salts, nonces) break determinism. We can seed these globally by adding `LOCAL-ONLY-DEBUG-` events to `pre_tick.validated`.

Todo: specify the events and their data format.

#### Deterministic Simulation

To simulate multiple steps in time over the network, with latency and packet loss, we can introduce `simulate`, a function that consumes a `network_conditions` function, a `pre_tick` state, an interval `t_ms` and a number of iterations `i` and returns a `post_tick` state.

Note: `simulate` operates on only one client, but since a client can contain an arbitrary number of peers joined to an arbitrary number of networks (including many peers on the same network, if desired) we can use a single client to model many networks, a single large network, or a combination.

At each iteration, `simulate` runs `tick(pre_tick)`, decrements `i`.

Then, in a key step, it appends `network_conditions(pre_tick, post_tick.outgoing, t_ms)` to `post_tick.incoming` before passing the entire modified `post_sim` object back into `tick`.

`network-conditions` has access to all client state, and it can apply arbitrary transformations on `outgoing[]`, but the most basic one would be to randomly drop some packets, or add an `arrives_at_ms` with a larger value than `t` to simulate latency or jitter.

Simulate can also save the state at each `tick` in a `simulations` table for inspection and debugging, log at which `tick` an error results, and log state diffs at errors.

#### User Behavior Simulation

Future refinements can add a `user_behavior` function passable to `simulate` that consumes a `post-tick` state and passes a new array of `api_calls[]` to the next state, to simulate behavior such as users sending messages, downloading blobs, scrolling with lazy loading, adding other users, etc.

#### Property-based Testing

We can augment `tick` to run property-based tests, checking that the pre and post states conform to invariants, and that the transformation does too.

### Full Device Linking

In some products, users may want to be able to automatically link *every* network they've joined on *any* device across *all* their devices, e.g. when they purchase a new device. In this case, each device can join a "meta" network with the user's other devices and automatically invite not-yet-joined devices to new networks (and, when invited, automatically join them). For simplicity we do not consider this case here.

### Efficient Blocking and Unblocking

Checking all blocked events on every event receipt would be inefficient, so instead, after validation each event type's processor searches for events it may unblock.

Recursively resolving all depdendencies and their dependencies etc. could create unexpected performance impacts, so instead we simply move potentially-unblocked events back to incoming where they will be processed again as if freshly received.

TODO: there is a subtlety here around transit-layer encryption, since we want to purge those keys quickly and not keep them around. So when we say event data we mean the canonical data and not the transit-layer encrypted data since that's ephemeral. It might make sense to handle transit-layer encryption outside of tick in its own in-memory function. This also protects the database from events from total strangers. 

We can also keep tables indexed by `user` and `group-id` for auth events, so that when we receive an auth event we can find the user it unblocks.

### Background iOS Push Notifications

We will have to run a separate instance of the client in iOS, but we want to use the same database. We can give the notification app extension access to the same database using standard iOS techniques.

This creates potential issues around locking.

When the main client (application) is running we can assume that `tick` is being triggered regularly and state is being updated. And the main application can itself trigger notifications if needed. In this case, when push notifications arrive we can block their access to the database.

If we want to use push notifications as a data source, for example in a situation where typical data access is censored or the internet is unavailable but push notifications are still working, we can get a bit more sophisticated and attempt to give the notification app extension concurrent access to the database. But we don't have to.

### Example Code

See: [README.md](./README.md) for examples.

## TODO

- complete list of local-only events for tracking last actions, keys, etc.
- 
