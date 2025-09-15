# Jobs and Reflectors Design

## Core Concept

Both **Jobs** and **Reflectors** follow the same pattern: query the database, generate envelopes. The only difference is their trigger:

- **Jobs**: Triggered by time (scheduled)
- **Reflectors**: Triggered by events (reactive)

Both are pure functions that take a query function and return envelopes.

## The Pattern

```python
# Job: (query_fn, params) -> List[Envelope]
def sync_job(query_fn: Callable, params: Dict) -> List[Dict]:
    """Scheduled: Query peers, generate sync requests."""
    peers = query_fn('get_active_peers', {'network_id': params['network_id']})
    return [create_sync_request(peer) for peer in peers]

# Reflector: (event, query_fn) -> List[Envelope]
def reflect_sync_request(event: Dict, query_fn: Callable) -> List[Dict]:
    """Reactive: Receive sync request, generate sync responses."""
    if event.get('is_outgoing'):
        return []

    events = query_fn('get_events_for_sync', {
        'network_id': event['network_id'],
        'limit': 100
    })

    return [create_sync_response(e, event['peer_id']) for e in events]
```

## Architecture

### 1. Job Scheduler
```python
# core/scheduler.py
class JobScheduler:
    def run_due_jobs(self, db: Connection) -> List[Dict]:
        """Check for due jobs, run them, return envelopes."""
        due_jobs = get_due_jobs(db)
        all_envelopes = []

        for job_name, params in due_jobs:
            job_fn = load_job_function(job_name)

            # Create read-only query function
            def query_fn(query_name: str, query_params: Dict):
                return run_query(db, query_name, query_params)

            # Run job to get envelopes
            envelopes = job_fn(query_fn, params)
            all_envelopes.extend(envelopes)

            # Mark job as run
            mark_job_complete(db, job_name)

        return all_envelopes
```

### 2. Reflector Handler
```python
# protocols/quiet/handlers/reflect.py
class ReflectHandler(Handler):
    """Runs reflectors for events that trigger responses."""

    def __init__(self):
        self.reflectors = self._load_reflectors()

    def _load_reflectors(self):
        """Auto-discover from events/*/reflectors.py"""
        reflectors = {}
        for event_type in ['sync', 'message', 'group']:
            module = import_module(f'protocols.quiet.events.{event_type}.reflectors')
            reflector_name = f'reflect_{event_type}_request'
            if hasattr(module, reflector_name):
                reflectors[f'{event_type}_request'] = getattr(module, reflector_name)
        return reflectors

    def filter(self, envelope: Dict) -> bool:
        return (envelope.get('event_type') in self.reflectors and
                envelope.get('event_plaintext'))

    def process(self, envelope: Dict, db: Connection) -> List[Dict]:
        event_type = envelope['event_type']
        reflector = self.reflectors[event_type]

        # Create read-only query function
        def query_fn(query_name: str, params: Dict):
            return run_query(db, query_name, params)

        # Run reflector to get new envelopes
        return reflector(envelope['event_plaintext'], query_fn)
```

## Example: Complete Rekeying Flow

Using multiple coordinated jobs for safe, eventual consistency:

### Job 1: Create Rekey Events
```python
# protocols/quiet/jobs/rekey.py
def rekey_creation_job(query_fn: Callable, params: Dict) -> List[Dict]:
    """Find events needing rekey, create rekey events."""
    events_to_rekey = query_fn('get_events_needing_rekey', {
        'reason': 'key_expiry'
    })

    rekey_envelopes = []
    for event in events_to_rekey:
        # Find clean key with appropriate TTL
        new_key = query_fn('get_clean_key_for_ttl', {
            'ttl_ms': event['ttl_ms']
        })

        if new_key:
            rekey_envelopes.append({
                'event_type': 'rekey',
                'event_plaintext': {
                    'original_event_id': event['event_id'],
                    'new_key_id': new_key['key_id'],
                    'new_ciphertext': seal_with_key(new_key, event['plaintext'])
                }
            })

    return rekey_envelopes
```

### Job 2: Delete Rekeyed Events
```python
# protocols/quiet/jobs/cleanup.py
def delete_rekeyed_events_job(query_fn: Callable, params: Dict) -> List[Dict]:
    """Delete events that have been successfully rekeyed."""
    rekeyed_events = query_fn('get_successfully_rekeyed_events', {})

    return [{
        'event_type': 'delete-event',
        'event_plaintext': {'event_id': event['original_event_id']}
    } for event in rekeyed_events]
```

### Job 3: Purge Unused Keys
```python
# protocols/quiet/jobs/purge.py
def purge_unused_keys_job(query_fn: Callable, params: Dict) -> List[Dict]:
    """Purge keys that no longer have any events using them."""
    unused_keys = query_fn('get_unused_keys_marked_for_purge', {})

    return [{
        'event_type': 'purge-key',
        'event_plaintext': {
            'key_id': key['key_id'],
            'secure_delete': True
        }
    } for key in unused_keys]
```

## Example: TTL Cleanup

```python
# protocols/quiet/jobs/ttl.py
def ttl_cleanup_job(query_fn: Callable, params: Dict) -> List[Dict]:
    """Delete events that have expired."""
    current_time_ms = int(time.time() * 1000)
    expired_events = query_fn('get_expired_events', {
        'current_time_ms': current_time_ms
    })

    deletion_envelopes = []
    for event in expired_events:
        # Create delete-message with longer TTL than original
        deletion_envelopes.append({
            'event_type': 'delete-message',
            'event_plaintext': {
                'message_id': event['event_id'],
                'ttl_ms': event['ttl_ms'] + 86400000  # +1 day
            }
        })

    return deletion_envelopes
```

## Job Configuration

```yaml
# protocols/quiet/jobs.yaml
jobs:
  # Sync every 3 seconds
  - name: sync_request
    function: sync_job
    frequency_ms: 3000
    params:
      network_id: "${NETWORK_ID}"

  # Rekeying pipeline (staggered for safety)
  - name: rekey_creation
    function: rekey_creation_job
    frequency_ms: 60000  # Every minute

  - name: delete_rekeyed
    function: delete_rekeyed_events_job
    frequency_ms: 65000  # 5 seconds after rekey

  - name: purge_keys
    function: purge_unused_keys_job
    frequency_ms: 70000  # 10 seconds after delete

  # TTL cleanup every 5 minutes
  - name: ttl_cleanup
    function: ttl_cleanup_job
    frequency_ms: 300000

  # Prekey replenishment every 10 minutes
  - name: prekey_replenish
    function: prekey_replenishment_job
    frequency_ms: 600000
```

## File Structure

```
protocols/quiet/
├── jobs/
│   ├── sync.py           # sync_job()
│   ├── rekey.py          # rekey_creation_job()
│   ├── cleanup.py        # delete_rekeyed_events_job()
│   ├── purge.py          # purge_unused_keys_job()
│   ├── ttl.py            # ttl_cleanup_job()
│   └── prekeys.py        # prekey_replenishment_job()
│
├── events/
│   ├── sync/
│   │   ├── reflectors.py # reflect_sync_request()
│   │   └── queries.py    # get_events_for_sync(), get_active_peers()
│   │
│   └── message/
│       ├── reflectors.py # reflect_message_reaction()
│       └── queries.py    # get_message_by_id()
│
└── handlers/
    └── reflect.py        # ReflectHandler
```

## Key Benefits

1. **Unified Pattern**: Jobs and reflectors follow same `(query_fn, ...) -> envelopes` pattern
2. **Pure Functions**: No side effects, just query and generate
3. **Query-Only Access**: Read-only database access via query functions
4. **Natural Safety**: Multi-stage jobs ensure safe ordering (rekey → delete → purge)
5. **Eventual Consistency**: No complex transactions needed
6. **Testable**: Pure functions are easy to test
7. **Discoverable**: Auto-discovery from file structure
8. **Extensible**: Add new jobs/reflectors without changing core

## Implementation Notes

### Query Functions
Queries are registered read-only functions that return data:
```python
@query('get_active_peers')
def get_active_peers(db: ReadOnlyConnection, params: Dict) -> List[Dict]:
    """Get all active peers for a network."""
    return db.execute("""
        SELECT peer_id, ip, port
        FROM addresses
        WHERE network_id = ? AND is_active = 1
    """, (params['network_id'],)).fetchall()
```

### Envelope Processing
All generated envelopes go through the normal pipeline:
- Commands generate envelopes
- Jobs generate envelopes
- Reflectors generate envelopes
- All envelopes are processed by handlers

### Handler Responsibilities
- **ReflectHandler**: Runs reflectors for incoming events
- **EventStoreHandler**: Stores events in database
- **DeleteHandler**: Processes delete-event envelopes
- **PurgeHandler**: Processes purge-key envelopes with secure deletion

## Summary

The jobs and reflectors pattern provides a clean, unified way to handle:
- **Scheduled operations** (sync, cleanup, maintenance)
- **Event-triggered responses** (sync responses, reactions)
- **Complex workflows** (multi-stage rekeying)
- **Protocol requirements** (forward secrecy, TTL, prekeys)

All while maintaining:
- Pure functions
- Read-only query access
- Eventual consistency
- Natural safety through ordering