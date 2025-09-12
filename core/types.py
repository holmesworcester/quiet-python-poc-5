"""Type definitions for Quiet Protocol POC 5"""

from typing import TypedDict, Literal, Any, Protocol, runtime_checkable, TypeVar, Generic, Type, get_args, get_origin, Union
from collections.abc import Callable

# Base types
EventType = str
EventId = str
PeerId = str
NetworkId = str
GroupId = str
KeyId = str
TransitKeyId = str
AddressId = str
UserId = str

# Operation types for deltas
OpType = Literal["insert", "update", "delete"]

# Envelope state flags
class EnvelopeState(TypedDict, total=False):
    """State flags that track envelope processing status"""
    deps_included_and_valid: bool
    sig_checked: bool
    validated: bool
    prevalidated: bool
    projected: bool
    self_created: bool
    self_signed: bool
    outgoing: bool
    outgoing_checked: bool
    stripped_for_send: bool
    write_to_store: bool
    missing_deps: bool
    unblocked: bool
    should_remove: bool
    is_group_member: bool

# Core envelope structure
class Envelope(TypedDict, total=False):
    """Main envelope structure that carries events through the pipeline"""
    # Event data
    event_plaintext: dict[str, Any]
    event_ciphertext: bytes
    event_type: EventType
    event_id: EventId
    
    # Identity/ownership
    self_created: bool
    peer_id: PeerId
    
    # Network/group context
    network_id: NetworkId
    group_id: GroupId
    
    # Dependencies
    deps: list[str]  # e.g., ["identity:abc123", "key:xyz789"]
    resolved_deps: dict[str, dict[str, Any]]
    missing_deps_list: list[str]
    
    # Secret data (never sent over network)
    secret: dict[str, Any]
    
    # Transit encryption
    transit_key_id: TransitKeyId
    transit_ciphertext: bytes
    transit_plaintext: dict[str, Any]
    
    # Event encryption
    event_key_id: KeyId
    
    # Network transport
    origin_ip: str
    origin_port: int
    dest_ip: str
    dest_port: int
    received_at: float
    due_ms: int
    raw_data: bytes
    
    # User/address context
    user_id: UserId
    address_id: AddressId
    
    # Processing state flags (from EnvelopeState)
    deps_included_and_valid: bool
    sig_checked: bool
    validated: bool
    prevalidated: bool
    projected: bool
    self_signed: bool
    outgoing: bool
    outgoing_checked: bool
    stripped_for_send: bool
    write_to_store: bool
    missing_deps: bool
    unblocked: bool
    should_remove: bool
    is_group_member: bool
    
    # Errors
    error: str

# Specialized envelope types for different pipeline stages
# Note: These are documentation types - we can't override TypedDict fields
# so we define them separately without inheritance

class NetworkEnvelope(TypedDict):
    """Envelope with required fields for network reception"""
    origin_ip: str
    origin_port: int
    received_at: float
    raw_data: bytes

class TransitEnvelope(TypedDict):
    """Envelope with required fields for transit decryption"""
    transit_key_id: TransitKeyId
    transit_ciphertext: bytes
    deps_included_and_valid: bool

class DecryptedEnvelope(TypedDict):
    """Envelope with required fields after decryption"""
    event_plaintext: dict[str, Any]
    event_type: EventType
    event_id: EventId
    peer_id: PeerId

class ValidatedEnvelope(TypedDict):
    """Envelope with required fields after validation"""
    event_plaintext: dict[str, Any]
    event_type: EventType
    event_id: EventId
    peer_id: PeerId
    sig_checked: Literal[True]
    validated: Literal[True]

class OutgoingEnvelope(TypedDict):
    """Envelope with required fields for outgoing messages"""
    outgoing: Literal[True]
    due_ms: int
    address_id: AddressId
    user_id: UserId
    peer_id: PeerId

class StrippedEnvelope(TypedDict):
    """Minimal envelope for network transmission"""
    transit_ciphertext: bytes
    transit_key_id: TransitKeyId
    due_ms: int
    dest_ip: str
    dest_port: int
    stripped_for_send: Literal[True]

# Delta operation structure
class Delta(TypedDict, total=False):
    """Database operation delta"""
    op: OpType
    table: str
    data: dict[str, Any]
    where: dict[str, Any]  # For update/delete operations
    sql: str  # For raw SQL operations
    params: list[Any]  # Parameters for raw SQL

# Function signatures as Protocol classes
@runtime_checkable
class CommandFunc(Protocol):
    """Protocol for event creation commands"""
    def __call__(self, params: dict[str, Any]) -> Envelope:
        """
        Create an unsigned event envelope from user parameters.
        
        Args:
            params: User-provided parameters (e.g., message content, channel_id)
            
        Returns:
            Envelope with event_plaintext, event_type, peer_id, and deps array
        """
        ...

@runtime_checkable
class ValidatorFunc(Protocol):
    """Protocol for event validators"""
    def __call__(self, envelope: Envelope) -> bool:
        """
        Validate event structure and business rules.
        
        Args:
            envelope: Full envelope with event_plaintext and resolved_deps
            
        Returns:
            True if valid, False otherwise
        """
        ...

@runtime_checkable
class ProjectorFunc(Protocol):
    """Protocol for event projectors"""
    def __call__(self, envelope: Envelope) -> list[Delta]:
        """
        Convert validated event to database deltas.
        
        Args:
            envelope: Validated envelope
            
        Returns:
            List of delta operations to apply
        """
        ...

@runtime_checkable
class RemoverFunc(Protocol):
    """Protocol for event removers"""
    def __call__(self, event_id: EventId, context: dict[str, Any]) -> bool:
        """
        Determine if event should be removed based on cascading deletions.
        
        Args:
            event_id: ID of event to check
            context: Removal context (e.g., {"removed_channels": ["chan123"]})
            
        Returns:
            True if event should be removed
        """
        ...

@runtime_checkable
class HandlerFunc(Protocol):
    """Protocol for pipeline handlers"""
    def __call__(self, envelope: Envelope) -> Envelope | None:
        """
        Process envelope and return transformed envelope.
        
        Args:
            envelope: Input envelope
            
        Returns:
            Transformed envelope or None if envelope should be dropped
        """
        ...

# Handler filter function
@runtime_checkable
class FilterFunc(Protocol):
    """Protocol for handler filter functions"""
    def __call__(self, envelope: Envelope) -> bool:
        """
        Determine if handler should process this envelope.
        
        Args:
            envelope: Envelope to check
            
        Returns:
            True if handler should process this envelope
        """
        ...

# Handler definition
class HandlerDef(TypedDict):
    """Handler definition with filter and handler function"""
    name: str
    filter: FilterFunc
    handler: HandlerFunc

# Type guards for runtime checking
def is_command(func: Callable) -> bool:
    """Check if function matches CommandFunc protocol"""
    return isinstance(func, CommandFunc)

def is_validator(func: Callable) -> bool:
    """Check if function matches ValidatorFunc protocol"""
    return isinstance(func, ValidatorFunc)

def is_projector(func: Callable) -> bool:
    """Check if function matches ProjectorFunc protocol"""
    return isinstance(func, ProjectorFunc)

def is_remover(func: Callable) -> bool:
    """Check if function matches RemoverFunc protocol"""
    return isinstance(func, RemoverFunc)

def is_handler(func: Callable) -> bool:
    """Check if function matches HandlerFunc protocol"""
    return isinstance(func, HandlerFunc)

# Helper to check for database access in functions
def _check_no_db_access(func: Callable) -> None:
    """
    Check that a function doesn't access database.
    This is a basic check looking for common patterns.
    """
    import inspect
    try:
        source = inspect.getsource(func)
        # Look for common database access patterns
        db_patterns = [
            'db.execute', 'cursor.execute', 'connection.execute',
            'db.commit', 'cursor.fetchone', 'cursor.fetchall',
            'sqlite3.connect', 'get_connection'
        ]
        for pattern in db_patterns:
            if pattern in source:
                raise ValueError(
                    f"{func.__name__} appears to access database (found '{pattern}'). "
                    f"Event functions must be pure functions without database access."
                )
    except OSError:
        # Can't get source (e.g., built-in function), skip check
        pass

# Decorator to enforce signatures with runtime checking
def command(func: Callable[[dict[str, Any]], Envelope]) -> Callable[[dict[str, Any]], Envelope]:
    """Decorator to mark and validate command functions"""
    import functools
    import inspect
    
    # Check signature at decoration time
    sig = inspect.signature(func)
    params = list(sig.parameters.keys())
    
    if len(params) != 1 or params[0] != 'params':
        raise TypeError(
            f"{func.__name__} must have signature (params: dict[str, Any]) -> Envelope, "
            f"got {sig}"
        )
    
    # Check for database access at decoration time
    _check_no_db_access(func)
    
    @functools.wraps(func)
    def wrapper(params: dict[str, Any]) -> Envelope:
        # Runtime type checking
        if not isinstance(params, dict):
            raise TypeError(f"Expected dict for params, got {type(params).__name__}")
        
        result = func(params)
        
        if not isinstance(result, dict):
            raise TypeError(f"{func.__name__} must return Envelope (dict), got {type(result).__name__}")
        
        # Ensure required command envelope fields
        required = {'event_plaintext', 'event_type', 'self_created', 'deps'}
        missing = required - set(result.keys())
        if missing:
            raise ValueError(f"{func.__name__} envelope missing required fields: {missing}")
        
        return result
    
    # Mark as command function
    wrapper._is_command = True
    
    return wrapper

def validator(func: Callable[[Envelope], bool]) -> Callable[[Envelope], bool]:
    """Decorator to mark and validate validator functions"""
    import functools
    import inspect
    
    # Check signature at decoration time
    sig = inspect.signature(func)
    params = list(sig.parameters.keys())
    
    if len(params) != 1 or params[0] != 'envelope':
        raise TypeError(
            f"{func.__name__} must have signature (envelope: Envelope) -> bool, "
            f"got {sig}"
        )
    
    # Check for database access at decoration time
    _check_no_db_access(func)
    
    @functools.wraps(func)
    def wrapper(envelope: Envelope) -> bool:
        # Runtime type checking
        if not isinstance(envelope, dict):
            raise TypeError(f"Expected Envelope (dict) for envelope, got {type(envelope).__name__}")
        
        result = func(envelope)
        
        if not isinstance(result, bool):
            raise TypeError(f"{func.__name__} must return bool, got {type(result).__name__}")
        
        return result
    
    return wrapper

def projector(func: Callable[[Envelope], list[Delta]]) -> Callable[[Envelope], list[Delta]]:
    """Decorator to mark and validate projector functions"""
    import functools
    import inspect
    
    # Check signature at decoration time
    sig = inspect.signature(func)
    params = list(sig.parameters.keys())
    
    if len(params) != 1 or params[0] != 'envelope':
        raise TypeError(
            f"{func.__name__} must have signature (envelope: Envelope) -> list[Delta], "
            f"got {sig}"
        )
    
    # Check for database access at decoration time
    _check_no_db_access(func)
    
    @functools.wraps(func)
    def wrapper(envelope: Envelope) -> list[Delta]:
        # Runtime type checking
        if not isinstance(envelope, dict):
            raise TypeError(f"Expected Envelope (dict) for envelope, got {type(envelope).__name__}")
        
        result = func(envelope)
        
        if not isinstance(result, list):
            raise TypeError(f"{func.__name__} must return list[Delta], got {type(result).__name__}")
        
        # Validate each delta
        for i, delta in enumerate(result):
            if not isinstance(delta, dict):
                raise TypeError(f"{func.__name__} delta[{i}] must be dict, got {type(delta).__name__}")
            
            if 'op' not in delta or 'table' not in delta or 'data' not in delta:
                raise ValueError(f"{func.__name__} delta[{i}] missing required fields (op, table, data)")
            
            if delta['op'] not in ('insert', 'update', 'delete'):
                raise ValueError(f"{func.__name__} delta[{i}] invalid op: {delta['op']}")
        
        return result
    
    return wrapper

def remover(func: Callable[[EventId, dict[str, Any]], bool]) -> Callable[[EventId, dict[str, Any]], bool]:
    """Decorator to mark and validate remover functions"""
    import functools
    import inspect
    
    # Check signature at decoration time
    sig = inspect.signature(func)
    params = list(sig.parameters.keys())
    
    if len(params) != 2 or params[0] != 'event_id' or params[1] != 'context':
        raise TypeError(
            f"{func.__name__} must have signature (event_id: EventId, context: dict[str, Any]) -> bool, "
            f"got {sig}"
        )
    
    @functools.wraps(func)
    def wrapper(event_id: EventId, context: dict[str, Any]) -> bool:
        # Runtime type checking
        if not isinstance(event_id, str):
            raise TypeError(f"Expected str for event_id, got {type(event_id).__name__}")
        
        if not isinstance(context, dict):
            raise TypeError(f"Expected dict for context, got {type(context).__name__}")
        
        result = func(event_id, context)
        
        if not isinstance(result, bool):
            raise TypeError(f"{func.__name__} must return bool, got {type(result).__name__}")
        
        return result
    
    return wrapper

def handler(name: str, filter_func: FilterFunc):
    """Decorator to mark and validate handler functions"""
    def decorator(func: Callable[[Envelope], Envelope | None]) -> HandlerDef:
        # We can't use is_handler check here since Protocols don't work well with runtime checking
        return {
            "name": name,
            "filter": filter_func,
            "handler": func  # type: ignore
        }
    return decorator

# Runtime validation functions
def validate_envelope_fields(envelope: Envelope, required_fields: set[str]) -> bool:
    """
    Validate that envelope has required fields with non-None values.
    
    Args:
        envelope: Envelope to validate
        required_fields: Set of field names that must exist and not be None
        
    Returns:
        True if all required fields exist and are not None
    """
    return all(field in envelope and envelope.get(field) is not None 
               for field in required_fields)

def get_required_fields(envelope_type: Type[Any]) -> set[str]:
    """
    Extract required fields from an envelope type's annotations.
    
    Args:
        envelope_type: The envelope type class
        
    Returns:
        Set of field names that are required (not Optional)
    """
    required = set()
    for field, annotation in envelope_type.__annotations__.items():
        # Skip if field is Optional (Union with None)
        origin = get_origin(annotation)
        if origin is Union:
            args = get_args(annotation)
            if type(None) in args:
                continue
        required.add(field)
    return required

TEnvelope = TypeVar('TEnvelope')

def cast_envelope(envelope: Envelope, target_type: Type[TEnvelope]) -> TEnvelope:
    """
    Safe cast envelope to target type with runtime validation.
    
    Args:
        envelope: Envelope to cast
        target_type: Target envelope type
        
    Returns:
        The same envelope, type-cast to target_type
        
    Raises:
        TypeError: If envelope is missing required fields
    """
    required = get_required_fields(target_type)
    missing = [f for f in required if f not in envelope or envelope.get(f) is None]
    
    if missing:
        raise TypeError(
            f"Envelope missing required fields for {target_type.__name__}: "
            f"{', '.join(missing)}"
        )
    
    return envelope  # type: ignore

# Type guards for envelope types
def is_network_envelope(envelope: Envelope) -> bool:
    """Check if envelope has NetworkEnvelope required fields"""
    return validate_envelope_fields(envelope, {'origin_ip', 'origin_port', 'received_at', 'raw_data'})

def is_transit_envelope(envelope: Envelope) -> bool:
    """Check if envelope has TransitEnvelope required fields"""
    return validate_envelope_fields(envelope, {'transit_key_id', 'transit_ciphertext'})

def is_decrypted_envelope(envelope: Envelope) -> bool:
    """Check if envelope has DecryptedEnvelope required fields"""
    return validate_envelope_fields(envelope, {'event_plaintext', 'event_type', 'event_id', 'peer_id'})

def is_validated_envelope(envelope: Envelope) -> bool:
    """Check if envelope has ValidatedEnvelope required fields"""
    return (is_decrypted_envelope(envelope) and 
            envelope.get('sig_checked') is True and 
            envelope.get('validated') is True)

def is_outgoing_envelope(envelope: Envelope) -> bool:
    """Check if envelope has OutgoingEnvelope required fields"""
    return (envelope.get('outgoing') is True and
            validate_envelope_fields(envelope, {'due_ms', 'address_id', 'user_id', 'peer_id'}))