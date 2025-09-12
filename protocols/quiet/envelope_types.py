"""
Envelope type definitions for the pipeline.

These TypedDict classes define the shape of envelopes as they flow through handlers.
While Python's type system isn't as strict as TypeScript, these provide documentation
and enable runtime validation.
"""

from typing import TypedDict, Any, Dict, List, Optional, Union, Literal
from typing_extensions import NotRequired


# Dependency types
class ValidatedEvent(TypedDict):
    """A validated event dependency."""
    event_plaintext: Dict[str, Any]
    event_type: str
    event_id: str
    validated: Literal[True]

class IdentityDep(TypedDict):
    """Identity dependency with optional local private key."""
    event_plaintext: Dict[str, Any]
    event_type: Literal["identity"]
    event_id: str
    validated: Literal[True]
    local_metadata: NotRequired[Dict[str, Any]]  # Contains private_key if local

class TransitKeyDep(TypedDict):
    """Transit key dependency (local secret, not an event)."""
    transit_secret: bytes
    network_id: str

class AddressDep(TypedDict):
    """Address dependency for routing."""
    ip: str
    port: int
    public_key: NotRequired[str]

# Union type for all possible dependencies
ResolvedDep = Union[ValidatedEvent, IdentityDep, TransitKeyDep, AddressDep]


class NetworkData(TypedDict):
    """Raw network data received from the network."""
    origin_ip: str
    origin_port: int
    received_at: int
    raw_data: bytes


class TransitEnvelope(TypedDict):
    """Envelope with transit-layer encryption."""
    transit_key_id: str
    transit_ciphertext: bytes
    origin_ip: NotRequired[str]
    origin_port: NotRequired[int]
    received_at: NotRequired[int]


class BaseEnvelope(TypedDict, total=False):
    """Base envelope that can contain any fields."""
    # Common fields
    event_plaintext: Dict[str, Any]
    event_ciphertext: bytes
    event_type: str
    event_id: str
    
    # State flags
    deps_included_and_valid: bool
    sig_checked: bool
    validated: bool
    projected: bool
    stored: bool
    write_to_store: bool
    self_created: bool
    outgoing: bool
    outgoing_checked: bool
    stripped_for_send: bool
    should_remove: bool
    is_group_member: bool
    unblocked: bool
    
    # Data fields
    deps: List[str]
    resolved_deps: Dict[str, Any]
    missing_deps: bool
    missing_dep_list: List[str]
    local_metadata: Dict[str, Any]
    deltas: List[Dict[str, Any]]
    error: str
    
    # Network fields
    transit_key_id: str
    transit_ciphertext: bytes
    event_key_id: str
    network_id: str
    key_id: str
    group_id: str
    peer_id: str
    origin_ip: str
    origin_port: int
    received_at: int
    dest_ip: str
    dest_port: int
    due_ms: int


# Specific envelope types for different pipeline stages

class NeedsDepsEnvelope(TypedDict, total=False):
    """Envelope that needs dependency resolution."""
    deps: List[str]
    deps_included_and_valid: Union[bool, Literal[False]]
    unblocked: bool


class ResolvedDepsEnvelope(TypedDict):
    """Envelope with resolved dependencies."""
    deps_included_and_valid: Literal[True]
    resolved_deps: Dict[str, Any]


class MissingDepsEnvelope(TypedDict):
    """Envelope with missing dependencies."""
    missing_deps: Literal[True]
    missing_dep_list: List[str]


class TransitEncryptedEnvelope(TypedDict):
    """Envelope with transit encryption and resolved deps."""
    deps_included_and_valid: Literal[True]
    transit_key_id: str
    transit_ciphertext: bytes
    resolved_deps: Dict[str, Any]


class EventEncryptedEnvelope(TypedDict):
    """Envelope after transit decryption."""
    network_id: str
    event_key_id: str
    event_ciphertext: bytes
    event_id: str
    write_to_store: Literal[True]


class EventWithId(TypedDict):
    """Envelope with event_id for early removal check."""
    event_id: str
    should_remove: NotRequired[bool]
    event_type: NotRequired[str]


class DecryptedEventWithType(TypedDict):
    """Decrypted event for content-based removal check."""
    event_id: str
    event_plaintext: Dict[str, Any]
    event_type: str
    should_remove: NotRequired[bool]


class EncryptedEvent(TypedDict):
    """Encrypted event ready for decryption."""
    deps_included_and_valid: Literal[True]
    should_remove: Literal[False]
    event_key_id: str
    event_ciphertext: NotRequired[bytes]
    resolved_deps: Dict[str, Any]


class UnsealedKeyEvent(TypedDict):
    """Unsealed key event."""
    event_type: Literal["key"]
    key_id: str
    unsealed_secret: bytes
    group_id: str
    write_to_store: Literal[True]


class DecryptedEvent(TypedDict):
    """Decrypted event with plaintext."""
    event_plaintext: Dict[str, Any]
    event_type: str
    write_to_store: Literal[True]


class StorableEvent(TypedDict):
    """Event ready for storage."""
    write_to_store: Literal[True]
    event_id: NotRequired[str]
    event_ciphertext: NotRequired[bytes]
    event_plaintext: NotRequired[Dict[str, Any]]
    key_id: NotRequired[str]


class OutgoingTransitEnvelope(TypedDict):
    """Strict type for outgoing network data - ONLY what goes on the wire."""
    transit_ciphertext: bytes
    transit_key_id: str
    dest_ip: str
    dest_port: int
    due_ms: NotRequired[int]
    # That's it! No event data, no metadata, no secrets


class PlaintextEvent(TypedDict, total=False):
    """Event with plaintext for signature checking."""
    event_plaintext: Dict[str, Any]
    sig_checked: bool
    resolved_deps: Dict[str, Any]


class GroupEvent(TypedDict, total=False):
    """Event with group membership."""
    event_plaintext: Dict[str, Any]
    is_group_member: bool


class ValidatableEvent(TypedDict):
    """Event ready for validation."""
    event_plaintext: Dict[str, Any]
    event_type: str
    sig_checked: Literal[True]
    is_group_member: NotRequired[Literal[True]]
    resolved_deps: NotRequired[Dict[str, Any]]


class ValidatedOrBlockedEvent(TypedDict, total=False):
    """Validated or blocked event for unblocking."""
    validated: Literal[True]
    missing_deps: Literal[True]
    event_id: str


class ProjectableEvent(TypedDict):
    """Validated event ready for projection."""
    validated: Literal[True]
    event_type: str
    event_plaintext: Dict[str, Any]


class ProjectedEvent(ProjectableEvent):
    """Event after projection."""
    projected: Literal[True]
    deltas: List[Dict[str, Any]]


# Creation pipeline types

class CommandEnvelope(TypedDict):
    """Envelope created by a command."""
    event_plaintext: Dict[str, Any]
    event_type: str
    self_created: Literal[True]
    deps: List[str]


class SignableEnvelope(TypedDict):
    """Envelope ready for signing."""
    event_plaintext: Dict[str, Any]
    self_created: Literal[True]
    deps_included_and_valid: Literal[True]
    resolved_deps: Dict[str, Any]


class SignedEnvelope(SignableEnvelope):
    """Envelope after signing."""
    event_plaintext: Dict[str, Any]  # Now includes signature


class SignableOrVerifiableEvent(TypedDict, total=False):
    """Event that needs signing or verification."""
    event_plaintext: Dict[str, Any]
    sig_checked: bool
    self_created: bool
    deps_included_and_valid: Literal[True]
    resolved_deps: Dict[str, Any]


class ValidatedPlaintext(TypedDict):
    """Validated plaintext ready for encryption."""
    validated: Literal[True]
    event_plaintext: Dict[str, Any]
    event_ciphertext: NotRequired[None]


class EncryptedEventOutput(TypedDict):
    """Event after encryption."""
    event_ciphertext: bytes
    event_key_id: str
    event_id: str
    write_to_store: Literal[True]


# Outgoing pipeline types

class SendParams(TypedDict):
    """Parameters for sending an event."""
    event_id: str
    peer_id: str
    due_ms: NotRequired[int]


class OutgoingEnvelope(TypedDict):
    """Envelope marked for outgoing."""
    outgoing: Literal[True]
    deps: List[str]
    deps_included_and_valid: Literal[False]


class OutgoingWithDeps(TypedDict):
    """Outgoing envelope with resolved dependencies."""
    outgoing: Literal[True]
    deps_included_and_valid: Literal[True]
    resolved_deps: Dict[str, Any]
    outgoing_checked: NotRequired[None]


class OutgoingEncrypted(TypedDict):
    """Outgoing envelope with event encryption."""
    outgoing_checked: Literal[True]
    event_ciphertext: bytes
    transit_key_id: str
    resolved_deps: Dict[str, Any]


class TransitEncrypted(TypedDict):
    """Envelope with transit encryption."""
    transit_ciphertext: bytes
    transit_key_id: str
    dest_ip: NotRequired[str]
    dest_port: NotRequired[int]
    due_ms: NotRequired[int]


class PreStrippedEnvelope(TypedDict):
    """Envelope before stripping for send."""
    transit_ciphertext: bytes
    transit_key_id: str
    dest_ip: NotRequired[str]
    dest_port: NotRequired[int]
    due_ms: NotRequired[int]


class StrippedEnvelope(TypedDict):
    """Envelope stripped for network send."""
    transit_ciphertext: bytes
    transit_key_id: str
    due_ms: int
    dest_ip: str
    dest_port: int
    stripped_for_send: Literal[True]


def validate_envelope_fields(envelope: Dict[str, Any], required_fields: List[str]) -> bool:
    """Validate that an envelope contains required fields."""
    return all(field in envelope for field in required_fields)


def cast_envelope(envelope: Dict[str, Any], target_type: type) -> Dict[str, Any]:
    """
    Cast envelope to a specific type with validation.
    This is mainly for documentation - Python doesn't enforce at runtime.
    """
    # In a real implementation, we could validate against TypedDict fields
    return envelope