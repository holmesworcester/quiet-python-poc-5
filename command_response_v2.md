# Command Response Design v2: Command-Controlled Response Shaping

## Key Insight

Commands should control their own response shaping logic, having access to:
1. All envelopes they created (via request_id)
2. Optional follow-up queries after pipeline completion
3. Custom logic to shape the final API response

## Examples of Pipeline Data Commands Might Need

Beyond just IDs, commands may need to extract:

### 1. **Dependency Resolution**
- **create_message**: Which events were waiting for this message? Did it unblock any pending events?
- **create_key**: What events can now be decrypted with this key?

### 2. **Validation & Error Details**
- **join_network**: Did validation fail for any specific reason? Wrong network? Already a member?
- **create_channel**: Permission denied? Parent group doesn't exist?

### 3. **Encryption & Key Information**
- **create_invite**: What's the actual encrypted invite payload? What keys were embedded?
- **create_transit_secret**: What's the public key portion for sharing?
- **create_key**: The actual key material that needs to be distributed to group members

### 4. **Side Effects & Cascading Changes**
- **remove_user**: What groups/channels were they removed from? What messages were affected?
- **create_group**: What auto-generated channels were created? What permissions were set?
- **join_network**: What groups/channels was the user auto-added to?

### 5. **Network & Storage Confirmation**
- **create_message**: Was it queued for network delivery? To which peers?
- **Any event**: What's the final stored event_id? What timestamp was assigned?

### 6. **Membership & Permissions**
- **create_channel**: Who has access? What's the membership list?
- **add_user**: What permissions were granted? What existing permissions were inherited?

## Proposed Design

### Command Definition with Response Handler

```python
# In protocols/quiet/events/message/commands.py

@command
def create_message(params: Dict[str, Any], db: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Create a message in a channel."""
    # ... existing envelope creation logic ...

    return envelopes


@command_response
def create_message_response(
    request_id: str,
    envelopes: List[Dict[str, Any]],
    db: sqlite3.Connection
) -> Dict[str, Any]:
    """
    Shape the response for create_message command.
    This runs after pipeline processing completes.
    """
    # Find the message envelope
    message_envelope = next(
        (e for e in envelopes if e.get('event_type') == 'message'),
        None
    )

    if not message_envelope:
        return {'error': 'Message creation failed', 'envelopes': envelopes}

    # Extract key information from processed envelope
    response = {
        'message_id': message_envelope.get('event_id'),
        'channel_id': message_envelope['event_plaintext'].get('channel_id'),
        'created_at': message_envelope.get('stored_at'),
        'validated': message_envelope.get('validated', False),
        'stored': message_envelope.get('stored', False)
    }

    # Check for any errors
    if message_envelope.get('error'):
        response['error'] = message_envelope['error']
        return response

    # Optional: Run a query to get recent messages
    if response['channel_id'] and response['stored']:
        cursor = db.execute("""
            SELECT m.message_id, m.content, m.author_id, m.created_at
            FROM messages m
            WHERE m.channel_id = ?
            ORDER BY m.created_at DESC
            LIMIT 20
        """, (response['channel_id'],))

        response['recent_messages'] = [
            dict(zip(['message_id', 'content', 'author_id', 'created_at'], row))
            for row in cursor.fetchall()
        ]

    return response
```

### Complex Example: create_invite

```python
@command_response
def create_invite_response(
    request_id: str,
    envelopes: List[Dict[str, Any]],
    db: sqlite3.Connection
) -> Dict[str, Any]:
    """
    Extract the invite code and encrypted payload from processed envelopes.
    """
    invite_envelope = next(
        (e for e in envelopes if e.get('event_type') == 'invite'),
        None
    )

    if not invite_envelope:
        return {'error': 'Invite creation failed'}

    # The invite code is generated during encryption
    invite_code = invite_envelope.get('invite_code')

    # The encrypted payload contains network bootstrap info
    encrypted_payload = invite_envelope.get('transit_payload', {})

    # Extract network metadata
    network_id = invite_envelope['event_plaintext'].get('network_id')
    inviter_id = invite_envelope['event_plaintext'].get('inviter_id')
    expires_at = invite_envelope['event_plaintext'].get('expires_at')

    # Get additional context about the network
    cursor = db.execute("""
        SELECT n.name, g.group_id, g.name as group_name
        FROM networks n
        LEFT JOIN groups g ON g.network_id = n.network_id
        WHERE n.network_id = ?
    """, (network_id,))

    network_info = cursor.fetchone()

    return {
        'invite_code': invite_code,
        'network_id': network_id,
        'inviter_id': inviter_id,
        'expires_at': expires_at,
        'network': {
            'name': network_info[0] if network_info else None,
            'default_group': network_info[1] if network_info else None
        },
        'encrypted_payload': encrypted_payload,  # For QR codes, etc.
        'share_url': f"quiet://invite/{invite_code}"  # Convenience field
    }
```

### API Integration

```python
# In core/api.py

def _execute_command(self, operation_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Execute a command through the pipeline runner."""
    from core.commands import command_registry
    import uuid

    # Generate unique request ID
    request_id = str(uuid.uuid4())

    # Get database connection
    db = get_connection(str(self.db_path))

    try:
        # Execute command through registry
        envelopes = command_registry.execute(operation_id, params or {}, db)

        # Add request_id to all envelopes
        for envelope in envelopes:
            envelope['request_id'] = request_id

        # Store initial envelopes for later retrieval
        self._store_request_envelopes(db, request_id, envelopes)

        # Run the pipeline to process the envelopes
        if envelopes:
            self.runner.run(
                protocol_dir=str(self.protocol_dir),
                input_envelopes=envelopes
            )

        # Retrieve all processed envelopes for this request
        processed_envelopes = self._get_request_envelopes(db, request_id)

        # Look for a response handler for this command
        response_handler = command_registry.get_response_handler(operation_id)

        if response_handler:
            # Let the command shape its own response
            result = response_handler(request_id, processed_envelopes, db)
        else:
            # Fallback: return basic envelope data
            result = {
                'request_id': request_id,
                'envelopes': processed_envelopes
            }

        return result

    finally:
        # Clean up stored envelopes
        self._cleanup_request_envelopes(db, request_id)
        db.close()
```

### Pipeline Envelope Tracking

```python
# In core/pipeline.py or handlers

def update_envelope_in_request(db: sqlite3.Connection, envelope: Dict[str, Any]):
    """
    Update the stored envelope for a request as it moves through the pipeline.
    This allows commands to see the full processing history.
    """
    if 'request_id' not in envelope:
        return

    request_id = envelope['request_id']
    event_type = envelope.get('event_type')

    # Update the envelope in storage with its current state
    db.execute("""
        UPDATE request_envelopes
        SET envelope_data = ?
        WHERE request_id = ? AND event_type = ?
    """, (json.dumps(envelope), request_id, event_type))
```

## Benefits

1. **Maximum flexibility**: Commands control exactly what data to return
2. **Full pipeline visibility**: Access to all envelope states and transformations
3. **Error handling**: Commands can interpret and surface specific errors
4. **Custom queries**: Each command can run appropriate follow-up queries
5. **Clean separation**: Response logic stays with command definition
6. **Progressive enhancement**: Commands without response handlers still work

## Implementation Steps

1. Add `request_envelopes` table to store envelope states
2. Create `@command_response` decorator
3. Update pipeline handlers to update envelope state in storage
4. Modify API to call response handlers after pipeline
5. Migrate existing commands to add response handlers

## Example Use Cases

### Creating a Group with Auto-Setup
```python
@command_response
def create_group_response(request_id: str, envelopes: List[Dict[str, Any]], db):
    # Find all the envelopes we created
    group_env = next((e for e in envelopes if e['event_type'] == 'group'), None)
    channel_envs = [e for e in envelopes if e['event_type'] == 'channel']
    key_env = next((e for e in envelopes if e['event_type'] == 'key'), None)

    return {
        'group': {
            'id': group_env.get('event_id'),
            'name': group_env['event_plaintext']['name']
        },
        'channels': [
            {'id': e.get('event_id'), 'name': e['event_plaintext']['name']}
            for e in channel_envs
        ],
        'encryption_key': key_env.get('key_material') if key_env else None,
        'members_added': len([e for e in envelopes if e['event_type'] == 'add'])
    }
```

### Network Bootstrap Info
```python
@command_response
def join_network_response(request_id: str, envelopes: List[Dict[str, Any]], db):
    # Show everything that was set up for the new user
    return {
        'identity': {...},
        'groups_joined': [...],
        'channels_accessible': [...],
        'keys_received': [...],
        'pending_messages': [...]  # Messages they can now decrypt
    }
```

## Conclusion

By allowing commands to control their own response shaping with full access to processed envelopes, we get maximum flexibility while keeping related logic together. This approach handles both simple cases (just return the ID) and complex cases (return a rich object with context, errors, and related data).