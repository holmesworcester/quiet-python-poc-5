# Unified Crypto Handler Design

## Current State: Two Separate Handlers

### event_crypto handler
- **Decrypt filter**: `deps_included_and_valid` AND has `key_ref` AND no `event_plaintext`
- **Encrypt filter**: `validated` AND has `event_plaintext` AND no `event_ciphertext`
- **Seal/unseal**: Currently special-cased but should be standard peer sealing

### transit_crypto handler
- **Decrypt filter**: `deps_included_and_valid` AND has `transit_key_id` AND `transit_ciphertext` AND no `key_ref`
- **Encrypt filter**: `outgoing_checked` AND has `event_ciphertext` AND `transit_key_id`
- **Note**: `transit_key_id` can reference either a `key_id` or `peer_id`

## Proposed: Single Unified Crypto Handler

### Benefits of Unification
1. **Unified crypto logic**: All crypto in one place (though may require multiple passes for dependency resolution)
2. **Clearer data flow**: One place for all crypto operations
3. **Network_id from transit keys only**: Extract network_id only from transit keys (not event keys) since removed members might still have old event keys

### Unified Filter Logic
```python
def filter_func(envelope: dict[str, Any]) -> bool:
    # Transit decrypt: has transit encryption
    if ('transit_key_id' in envelope and
        'transit_ciphertext' in envelope and
        'key_ref' not in envelope):
        return True

    # Event decrypt: has event encryption
    if ('key_ref' in envelope and
        'event_plaintext' not in envelope and
        envelope.get('deps_included_and_valid')):
        return True

    # Event encrypt: validated plaintext needs encryption
    if (envelope.get('validated') and
        'event_plaintext' in envelope and
        'event_ciphertext' not in envelope):
        return True

    # Transit encrypt: outgoing needs transit wrap
    if (envelope.get('outgoing_checked') and
        'event_ciphertext' in envelope and
        'transit_key_id' in envelope):
        return True

    # Seal/unseal operations
    if 'seal_to' in envelope or 'event_sealed' in envelope:
        return True

    return False
```

### Network ID Detection Strategy

**Important**: Only extract network_id from transit keys, not event keys (since removed members might still have old event keys).

#### From Transit Keys Only
```python
# transit_key_id can reference identity, peer, or key
transit_key_id = envelope['transit_key_id']

# Determine the type and extract network_id
if transit_key_id.startswith('identity:'):
    identity_data = resolved_deps.get(transit_key_id)
    network_id = identity_data['event_plaintext']['network_id']
elif transit_key_id.startswith('peer:'):
    peer_data = resolved_deps.get(transit_key_id)
    network_id = peer_data['event_plaintext']['network_id']
elif transit_key_id.startswith('key:'):
    # For ephemeral transit keys
    key_data = resolved_deps.get(transit_key_id)
    network_id = key_data['network_id']
```

#### NOT From Event Keys
Do not use event-layer keys for network_id detection as these are longer-lived and might be known to removed members.

### Processing Flow in Unified Handler

```python
def handler(envelope: dict[str, Any]) -> dict[str, Any]:
    # Phase 1: Transit decryption (if needed)
    if 'transit_ciphertext' in envelope and 'key_ref' not in envelope:
        envelope = decrypt_transit(envelope)
        # Extract network_id from transit key (identity)
        transit_key_id = envelope['transit_key_id']
        identity_data = envelope['resolved_deps'].get(f"identity:{transit_key_id}")
        if identity_data:
            envelope['network_id'] = identity_data['event_plaintext']['network_id']

    # Phase 2: Event decryption/unsealing (if needed)
    if 'key_ref' in envelope and 'event_plaintext' not in envelope:
        if envelope['key_ref']['kind'] == 'peer':
            envelope = unseal_key_event(envelope)
        else:
            envelope = decrypt_event(envelope)

    # Phase 3: Event encryption/sealing (if needed)
    if 'event_plaintext' in envelope and 'event_ciphertext' not in envelope:
        if 'seal_to' in envelope:
            envelope = seal_event(envelope)
        elif envelope.get('validated'):
            envelope = encrypt_event(envelope)

    # Phase 4: Transit encryption (if needed)
    if envelope.get('outgoing_checked') and 'transit_key_id' in envelope:
        envelope = encrypt_transit(envelope)
        # Transit envelope only has minimal fields
        return {
            'transit_ciphertext': envelope['transit_ciphertext'],
            'transit_key_id': envelope['transit_key_id'],
            'dest_ip': envelope.get('dest_ip'),
            'dest_port': envelope.get('dest_port'),
            'due_ms': envelope.get('due_ms')
        }

    return envelope
```

### Key Resolution Dependencies

For the unified handler to work with dependencies:

1. **Commands must declare all needed keys**:
   ```python
   # For sync-request (sealed to peer)
   envelope['deps'] = [
       f"identity:{identity_id}",  # For transit wrapping
       f"peer:{peer_id}"          # For sealing to peer
   ]

   # For group message
   envelope['deps'] = [
       f"identity:{identity_id}",  # For transit wrapping
       f"key:{key_id}"            # For event encryption
   ]
   ```

2. **resolve_deps provides all keys**:
   ```python
   envelope['resolved_deps'] = {
       "identity:id123": {...},  # Contains network_id
       "key:key456": {...},      # Contains group_id
       "peer:peer789": {...}     # Contains network_id
   }
   ```

3. **Handler uses resolved keys**:
   - No database access needed
   - All crypto material comes from resolved_deps
   - network_id can be extracted from any key type

## Implementation Considerations

### Pros of Unification
1. **Simpler pipeline**: One handler instead of two
2. **Clearer dependencies**: All crypto deps declared upfront
3. **Consistent patterns**: Sync-request becomes standard peer sealing

### Cons of Unification
1. **Complex handler**: More logic in one place
2. **Multiple passes**: May need to run through pipeline multiple times for dependency resolution
3. **Harder to test**: More paths through the code
4. **Less modular**: Can't easily swap transit/event crypto independently

### Migration Path
1. Create unified handler alongside existing ones
2. Test thoroughly with both running
3. Disable old handlers once unified is proven
4. Remove old handlers after stability period

## Recommendation

**Proceed with unification** because:
- Dependencies system already provides the abstraction needed
- Network ID detection becomes cleaner with resolved deps
- Reduces overall system complexity
- Natural fit with the "everything is an event" philosophy

The unified handler should:
1. Use only resolved_deps for keys (no DB access)
2. Extract network_id from the appropriate resolved dependency
3. Handle all crypto operations in a single pass
4. Return minimal envelope for transit-encrypted outgoing messages