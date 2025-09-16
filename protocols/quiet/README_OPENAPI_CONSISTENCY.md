# OpenAPI Consistency Strategy

## The Problem
OpenAPI operation IDs must match the actual function names in the code, or the API will break. Manual maintenance leads to drift.

## The Solution: Code as Source of Truth

### 1. Automatic Discovery
The validation script (`validate_openapi.py`) automatically discovers all operations by:
- Scanning for `@command` decorated functions in `events/*/commands.py`
- Scanning for `@query` decorated functions in `events/*/queries.py`
- Finding core operations in `core/identity.py` (pattern: `core_identity_*`)
- Including hardcoded system operations

### 2. Naming Convention
All operations follow: `{event_type}.{function_name}`
- Example: `user.join_as_user`, `peer.create_peer`, `core.identity_create`
- No exceptions, no mappings, no transformations

### 3. Validation in CI/CD
Add to your CI/CD pipeline:
```bash
python protocols/quiet/validate_openapi.py
```
This will fail the build if OpenAPI and code are out of sync.

### 4. Auto-fix Helper
When the validation fails, it suggests the exact OpenAPI definitions needed.
Copy these into `openapi.yaml` to fix the issue.

## How to Add New Operations

1. **Add the function** with appropriate decorator:
   ```python
   # In events/mytype/commands.py
   @command
   def do_something(params: Dict[str, Any]) -> dict:
       ...
   ```

2. **Run validation** to get the OpenAPI definition:
   ```bash
   python protocols/quiet/validate_openapi.py
   ```

3. **Copy suggested definition** into `openapi.yaml`

4. **Verify consistency**:
   ```bash
   python protocols/quiet/validate_openapi.py
   ```

## Benefits
- **Never out of sync**: Code and spec always match
- **Simple convention**: No complex mappings
- **Automated checking**: CI/CD catches drift immediately
- **Easy fixes**: Script tells you exactly what to add

## Implementation
The key is in `core/api.py`:
```python
# Simple consistent mapping: event_type.function_name
operation_id = f'{event_type}.{func_name}'
command_registry.register(operation_id, obj)
```

No special cases, no transformations. The function name IS the operation.