# Command Response Design

## Problem

Commands create events with empty IDs and signatures. Commands can't predict the final ID because they don't have dependencies or signing keys.

So the pipeline fills these in:
1. `resolve_deps` adds dependencies
2. `signature_handler` signs the event (with deps!)
3. `event_store` generates ID from hash of signed event

Events with id's get picked up by resolve deps, to unblock events with placeholders.

## Solution

Standard response shape with IDs from storage and optional query results:

```json
{
    "ids": {
        "network": "net_abc123...",
        "identity": "id_def456..."
    },
    "data": {
        // Optional query results
    }
}
```

## Constraints

**Only return IDs for event types with exactly one event.** If a command creates multiple events of the same type, that type is excluded from the `ids` object.

Examples:
- `create_network`: Creates 1 identity + 1 network → Returns both IDs
- `create_group`: Creates 1 group + 3 add events → Returns only group ID
- `bulk_import`: Creates many identity events → Returns no identity IDs


## Implementation

### 1. Pipeline Changes

```python
# In core/pipeline.py
class PipelineRunner:
    def run(self, protocol_dir: str, input_envelopes: List[Dict],
            db: sqlite3.Connection = None) -> Dict[str, str]:
        """
        Run pipeline, apply deltas, and return mapping of event_type -> event_id.
        """
        # ... existing pipeline logic ...
        # ... handlers process envelopes ...
        # ... deltas are collected ...

        # Apply all deltas to database
        if db and deltas:
            for delta in deltas:
                self._apply_delta(delta, db)
            db.commit()

        # Track stored events (after deltas applied)
        event_counts = {}
        event_ids = {}

        for envelope in processed_envelopes:
            if envelope.get('stored') and 'request_id' in envelope:
                event_type = envelope.get('event_type')
                event_id = envelope.get('event_id')

                # Count events per type
                event_counts[event_type] = event_counts.get(event_type, 0) + 1

                # Store first ID for each type
                if event_type not in event_ids:
                    event_ids[event_type] = event_id

        # Only return IDs for types with exactly one event
        stored_ids = {}
        for event_type, count in event_counts.items():
            if count == 1:
                stored_ids[event_type] = event_ids[event_type]

        return stored_ids
```

### 2. API Changes

```python
# In core/api.py
def _execute_command(self, operation_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Execute command and return standard response."""
    import uuid

    request_id = str(uuid.uuid4())
    db = get_connection(str(self.db_path))

    try:
        # Execute command
        result = command_registry.execute(operation_id, params or {}, db)
        envelopes = result.get('envelopes', [])
        post_query = result.get('post_query')

        # Track envelopes
        for envelope in envelopes:
            envelope['request_id'] = request_id

        # Run pipeline, apply deltas, and get stored IDs
        ids = {}
        if envelopes:
            ids = self.runner.run(
                protocol_dir=str(self.protocol_dir),
                input_envelopes=envelopes,
                db=db  # Pass db so pipeline can apply deltas
            )  # Returns {event_type: event_id} after deltas applied

        # Run post-query if specified (after deltas are in database)
        data = {}
        if post_query and ids:
            data = self.query_registry.execute(
                post_query['query'],
                post_query.get('params', {}),
                db
            )

        return {
            "ids": ids,
            "data": data
        }

    finally:
        db.close()
```

### 3. Command Pattern

```python
# Commands return envelopes and optional query
@command
def create_network(params: Dict[str, Any]) -> Dict[str, Any]:
    # ... create identity and network envelopes ...

    return {
        'envelopes': [identity_envelope, network_envelope],
        'post_query': {
            'query': 'network.get_summary',
            'params': {}  # Can use stored IDs
        }
    }

@command
def send_message(params: Dict[str, Any]) -> Dict[str, Any]:
    # ... create message envelope ...

    return {
        'envelopes': [message_envelope],
        'post_query': {
            'query': 'message.get_recent',
            'params': {'channel_id': params['channel_id'], 'limit': 20}
        }
    }
```


## Examples

```json
// create_network
{
    "ids": {
        "network": "net_abc123",
        "identity": "id_def456"
    },
    "data": {
        "name": "My Network",
        "members": 1
    }
}

// send_message
{
    "ids": {
        "message": "msg_123456"
    },
    "data": {
        "messages": [
            {"message_id": "msg_111", "content": "Hello"},
            {"message_id": "msg_123456", "content": "Hi!"}
        ]
    }
}
```