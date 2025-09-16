# Signature Verification Issue

## Current Implementation (Self-Attested)

Events contain their own public key:
```json
{
  "type": "message",
  "peer_id": "identity_id_here",  // Just an ID, not useful for verification
  "content": "Hello",
  "signature": "...",
  "public_key": "..."  // Self-provided public key
}
```

Verification process:
1. Extract `public_key` from the event itself
2. Verify `signature` matches that `public_key`
3. ✅ Signature is valid... but for which identity?

## The Problem

**We verify the math but not the identity!**

- Anyone can create an event with any `peer_id`
- They sign with their own key and include it
- Signature validates, but it's not from the claimed peer

## Proper Implementation (Peer-Verified)

Events should reference peer events:
```json
{
  "type": "message",
  "peer_id": "abc123",  // Event ID of peer event
  "content": "Hello",
  "signature": "..."
  // No public_key field - we get it from peer event
}
```

Verification process:
1. Resolve `peer:abc123` dependency
2. Get authoritative `public_key` from peer event
3. Verify `signature` against peer's public key
4. ✅ Signature is from the claimed peer

## Why It Works Now

The test passes because:
- We only create our own events
- We correctly sign them with our identity
- No malicious actors trying to impersonate

## Security Implications

Current approach is vulnerable to:
- **Impersonation**: Anyone can claim any peer_id
- **No peer validation**: peer_id is just a string
- **Trust model broken**: Can't trust event authorship

## Solution

1. **Always create peer events** when joining a network
2. **Reference peer event IDs** in peer_id field
3. **Resolve peer dependencies** before signature verification
4. **Verify against peer's public key**, not self-provided key

## Temporary Workaround

For testing/development, we could:
- Store public keys in a trusted registry
- Check that self-provided key matches registry
- Not suitable for production but OK for development