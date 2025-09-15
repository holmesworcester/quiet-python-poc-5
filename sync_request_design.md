# Sync Request Design

## Revised: Jobs Call Handlers Directly

```python
# core/scheduler.py

class JobScheduler:
    """Runs jobs by calling handlers directly."""

    def run_due_jobs(self, db: Connection, handlers: Dict[str, Handler]):
        jobs = load_job_definitions()

        for job in jobs:
            if is_job_due(db, job['name'], job['frequency_ms']):
                handler = handlers.get(job['handler'])
                if handler and hasattr(handler, 'run_job'):
                    # Call the handler's job method directly
                    envelopes = handler.run_job(db, job['params'])
                    # Inject envelopes into pipeline
                    pipeline.process(envelopes)

                mark_job_run(db, job['name'])
```

```python
# protocols/quiet/handlers/sync_handler.py

class SyncHandler(Handler):
    """Handles sync requests and responses."""

    def filter(self, envelope: Dict[str, Any]) -> bool:
        # Only process incoming sync requests
        return (envelope.get('event_type') == 'sync_request' and
                envelope.get('event_plaintext') and
                not envelope.get('is_outgoing'))

    def process(self, envelope: Dict[str, Any], db: Connection) -> List[Dict[str, Any]]:
        """Process incoming sync request: Query events and respond."""
        request = envelope['event_plaintext']

        # Query for events to send back
        events = db.execute("""
            SELECT event_id, event_type, event_ciphertext
            FROM events
            WHERE network_id = ?
            ORDER BY event_id
            LIMIT 100
        """, (request['network_id'],)).fetchall()

        # Generate response envelopes
        responses = []
        for event in events:
            response = {
                'event_id': event['event_id'],
                'event_type': event['event_type'],
                'event_ciphertext': event['event_ciphertext'],
                'seal_to': request['peer_id'],  # Seal to requester
                'is_outgoing': True,
                'in_response_to': request['request_id']
            }
            responses.append(response)

        return responses

    def run_job(self, db: Connection, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Job method: Generate sync requests to all peers."""
        network_id = params.get('network_id')

        # Get all active peer addresses
        peers = db.execute("""
            SELECT DISTINCT peer_id, ip, port
            FROM addresses
            WHERE network_id = ? AND is_active = TRUE
        """, (network_id,)).fetchall()

        # Generate sync request for each peer
        envelopes = []
        for peer_id, ip, port in peers:
            envelope = {
                'event_type': 'sync_request',
                'event_plaintext': {
                    'type': 'sync_request',
                    'request_id': generate_uuid(),
                    'network_id': network_id,
                    'peer_id': our_peer_id(),  # Our ID
                    'timestamp_ms': current_time_ms()
                },
                'seal_to': peer_id,  # Seal to target peer
                'is_outgoing': True,
                'dest_ip': ip,
                'dest_port': port
            }
            envelopes.append(envelope)

        return envelopes
```

## Key Design Points

1. **Jobs call handlers directly** - No pipeline indirection, scheduler just calls `handler.run_job()`
2. **Handlers track their own timing** - Each handler can check job_runs table if needed
3. **Same handler for both sides** - `SyncHandler` handles both job (generating requests) and processing (generating responses)
4. **Seal with `seal_to` field** - Setting `seal_to: peer_id` triggers sealing to that peer's public key
5. **Simple peer discovery** - Just query addresses table for all active peers

### Database Schema
```sql
-- Core responsibility - track job runs
CREATE TABLE IF NOT EXISTS job_runs (
    job_name TEXT PRIMARY KEY,
    last_run_ms INTEGER NOT NULL,
    run_count INTEGER DEFAULT 0
);
```

### Job Execution
- Scheduler runs jobs when due by calling handler methods directly
- Handlers can optionally check their own last-run times
- Job runs stored in DB survive app restarts/interruptions

## Sync Request Event

note: the real version of this will need to query event-store for ranges of id's, and it might need to query channels for most recent message id's too. (see ideal protocol design)

this makes me think a job is beefier than a command. 

deletion jobs will need to do queries too, to find ttl expired events etc. rekey jobs will be complex. i think these things need full tx access but i'm not sure. 

### Event Structure
```python
{
    'event_type': 'sync_request',
    'request_id': 'uuid',  # Unique request ID
    'network_id': 'network_123',
    'peer_id': 'peer_abc',  # Our peer ID
    'user_id': 'user_xyz',
    'transit_secret': 'secret_123',  # For matching responses
    'timestamp_ms': 1234567890,
    'target_peer_id': 'peer_def'  # Who we're syncing with
}
```

### Outgoing Sync Request Flow

1. **Job Trigger** (every 3000ms):
   - Job system calls `create_sync_request` command
   - Creates sync_request envelope

2. **Envelope Creation**:
   ```python
   def create_sync_request(network_id, peer_id, user_id, target_peer_id):
       return {
           'event_type': 'sync_request',
           'event_plaintext': {
               'request_id': generate_uuid(),
               'network_id': network_id,
               'peer_id': peer_id,
               'user_id': user_id,
               'transit_secret': generate_secret(),
               'timestamp_ms': current_time_ms(),
               'target_peer_id': target_peer_id
           },
           'is_outgoing': True,  # Mark for sending
           'seal_to': target_peer_id,  # Use seal, not encrypt
           'deps': []  # No dependencies
       }
   ```

3. **Processing**:
   - Event crypto handler sees `seal_to` field
   - Seals the event to target peer's public key
   - Transit crypto wraps with transit key
   - Send to network handler sends to peer's address

4. **Transit Secret Storage**:
   - Store `(request_id, transit_secret)` in memory/cache
   - Use to validate and decrypt responses
   - Expire after timeout (e.g., 30 seconds)

### Incoming Sync Request Flow

1. **Receipt**:
   - Receive from network handler gets packet
   - Transit crypto unwraps
   - Event crypto sees sealed envelope, opens with our private key
   - Validates it's a sync_request

2. **Processing** (new handler: `sync_request_handler.py`):
   ```python
   class SyncRequestHandler(Handler):
       def filter(self, envelope):
           return (
               envelope.get('event_type') == 'sync_request' and
               not envelope.get('is_outgoing')  # Incoming only
           )

       def process(self, envelope, db):
           event = envelope['event_plaintext']
           network_id = event['network_id']
           requester_peer_id = event['peer_id']

           # Fetch all events for this network
           events = fetch_network_events(db, network_id)

           # Create response envelopes
           responses = []
           for event in events:
               responses.append({
                   'event_id': event['event_id'],
                   'event_ciphertext': event['event_ciphertext'],
                   'seal_to': requester_peer_id,
                   'is_outgoing': True,
                   'in_response_to': event['request_id']
               })

           return responses
   ```

3. **Response Sending**:
   - Each event sealed to requester's peer_id
   - Marked with `in_response_to` for correlation
   - Sent through normal pipeline

### Sync Response Processing

1. **Receipt**:
   - Normal receive flow
   - Event crypto opens sealed envelope

2. **Deduplication**:
   - Check event_id against existing events
   - Only process new events

3. **Validation**:
   - Check `in_response_to` matches a known request_id
   - Verify transit_secret if included

## Handler Integration

### Job Scheduler

1. **JobScheduler** (in `core/scheduler.py`):
   - Runs as a separate component/thread
   - Periodically checks jobs.yaml
   - Queries job_runs table for due jobs
   - Emits `job_tick` envelopes into the pipeline
   - Updates job_runs table after execution

   Job tick envelopes look like:
   ```python
   {
       'type': 'job_tick',
       'job_name': 'sync_with_peers',
       'handler': 'sync',
       'params': {...},
       'timestamp_ms': 1234567890
   }
   ```

2. **SyncRequestHandler**:
   - Processes incoming sync_requests
   - Generates sync responses
   - Manages transit secrets

### Modified Handlers

1. **EventCryptoHandler**:
   - Add support for `seal_to` field (seal instead of encrypt)
   - Add support for opening sealed envelopes

2. **EventStoreHandler**:
   - Skip storing sync_request events
   - Check for duplicates before storing responses

## Database Considerations

### No Storage for Sync Requests
- Sync requests are ephemeral
- Not stored in events table
- Not projected to any tables

### Transit Secret Cache
- In-memory store or temporary table
- Key: request_id
- Value: transit_secret, timestamp
- TTL: 30 seconds

### Event Deduplication
- Events table should have unique constraint on event_id
- Or check before inserting

## Security Considerations

1. **Sealed vs Encrypted**:
   - Sealed: One-way, sender can't decrypt (for sync requests)
   - Encrypted: Two-way, sender can decrypt (for normal events)
   - Use peer's public key for sealing

2. **Transit Secrets**:
   - Unique per request
   - Short-lived (30 second TTL)
   - Used to correlate and validate responses

3. **Rate Limiting**:
   - Limit sync request frequency (min 3000ms)
   - Limit response size (max N events)
   - Prevent sync flooding

## Implementation Phases

### Phase 1: Job System
- [ ] Create core/jobs.py with DB functions
- [ ] Create protocols/quiet/jobs.yaml with job definitions
- [ ] Add job_runs table to core DB schema
- [ ] Create JobSchedulerHandler in core

### Phase 2: Sync Request Event
- [ ] Create sync_request event type
- [ ] Add create_sync_request command
- [ ] Register 3000ms job

### Phase 3: Crypto Support
- [ ] Add seal/open support to event crypto
- [ ] Handle seal_to field in envelopes

### Phase 4: Sync Handler
- [ ] Create SyncRequestHandler
- [ ] Implement request processing
- [ ] Implement response generation

### Phase 5: Response Processing
- [ ] Handle sync responses
- [ ] Implement deduplication
- [ ] Transit secret validation

## Example Flow

```
Peer A                          Peer B
  |                               |
  |-- Job triggers (3000ms) ----> |
  |   create_sync_request         |
  |                               |
  |-- Seal to Peer B -----------> |
  |   Send sync_request           |
  |                               |
  |                          Receive
  |                          Open sealed
  |                          Process request
  |                               |
  | <---- Send all events ------- |
  |       (sealed to Peer A)      |
  |                               |
  Receive                          |
  Open sealed                      |
  Dedupe events                    |
  Store new events                 |
  |                               |
```

## Configuration

```python
# Job configuration
SYNC_JOB_CONFIG = {
    'frequency_ms': 3000,  # Default 3 seconds
    'enabled': True,
    'max_events_per_response': 1000,
    'transit_secret_ttl_ms': 30000  # 30 seconds
}
```

## Testing Strategy

1. **Unit Tests**:
   - Job scheduling and execution
   - Sync request creation
   - Response generation
   - Deduplication logic

2. **Integration Tests**:
   - Full sync flow between two peers
   - Job trigger to response processing
   - Network simulator with sync

3. **Edge Cases**:
   - Expired transit secrets
   - Duplicate events
   - Large response sets
   - Network failures during sync