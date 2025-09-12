# Handler Pipeline Flow with Envelope Types

## Pipeline Order for Self-Created Events

### 1. Command → Initial Envelope
**Output Envelope:**
```typescript
{
  event_plaintext: { type, ...eventData },
  event_type: string,
  self_created: true,
  peer_id: string,
  network_id: string,
  deps: string[],
  local_metadata?: { private_key, public_key }
}
```

### 2. check_sig Handler
**Filter:** `event_plaintext` exists AND `sig_checked` is not true
**For self-created:** Signs the event
**For identity events:** Stores signing key first
**Output adds:**
- `signature` to event_plaintext
- `sig_checked: true`
- `self_signed: true` (for self-created)

### 3. resolve_deps Handler  
**Filter:** `event_plaintext` exists AND NOT `deps_included_and_valid`
**Output adds:**
- `deps_included_and_valid: true`
- `missing_deps: []`
- `resolved_deps: {}` (if deps exist)

### 4. event_store Handler
**Filter:** `sig_checked: true` AND no `event_id` AND not `stored`
**Output adds:**
- `event_id: string` (hash of signed plaintext)
- `stored: true`

### 5. validate Handler
**Filter:** `event_plaintext` AND `event_type` AND `sig_checked: true` AND not `validated`
**Output adds:**
- `validated: true` or error

### 6. project Handler
**Filter:** `validated: true` AND not `projected`
**Output adds:**
- `projected: true`
- `deltas: Delta[]`

## Issues Found

1. **validate handler** - The validator functions are being called incorrectly (getting 2 args instead of 1)
2. **Network event timing** - Network event can't be signed until identity event stores key
3. **Missing event_id validation** - Some handlers expect event_id before it's created

## Envelope Type Definitions Needed

```typescript
// After command creation
interface CommandEnvelope {
  event_plaintext: object;
  event_type: string;
  self_created: boolean;
  peer_id: string;
  network_id: string;
  deps: string[];
  local_metadata?: object;
}

// After check_sig
interface SignedEnvelope extends CommandEnvelope {
  sig_checked: boolean;
  self_signed?: boolean;
  event_plaintext: object & { signature: string };
}

// After resolve_deps
interface ResolvedEnvelope extends SignedEnvelope {
  deps_included_and_valid: boolean;
  missing_deps: string[];
  resolved_deps?: object;
}

// After event_store
interface StoredEnvelope extends ResolvedEnvelope {
  event_id: string;
  stored: boolean;
}

// After validate
interface ValidatedEnvelope extends StoredEnvelope {
  validated: boolean;
}

// After project
interface ProjectedEnvelope extends ValidatedEnvelope {
  projected: boolean;
  deltas: Delta[];
}
```