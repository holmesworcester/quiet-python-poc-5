"""
Event type registry with typed data structures for each event type.
"""

from typing import TypedDict, Type, Literal, Optional, Any
from dataclasses import dataclass

# Event-specific data types using TypedDict for strict typing

class IdentityEventData(TypedDict):
    """Identity event data structure"""
    type: Literal["identity"]
    peer_id: str
    network_id: str
    name: str
    created_at: int
    signature: str

class NetworkEventData(TypedDict):
    """Network event data structure"""
    type: Literal["network"]
    network_id: str
    creator_id: str
    name: str
    created_at: int
    signature: str

class KeyEventData(TypedDict):
    """Key event data structure"""
    type: Literal["key"]
    key_id: str
    peer_id: str
    network_id: str
    group_id: Optional[str]
    sealed_key: str  # Encrypted key data
    created_at: int
    signature: str

class TransitSecretEventData(TypedDict):
    """Transit secret event data structure"""
    type: Literal["transit_secret"]
    transit_key_id: str
    peer_id: str
    network_id: str
    created_at: int
    signature: str

class GroupEventData(TypedDict):
    """Group event data structure"""
    type: Literal["group"]
    group_id: str
    network_id: str
    creator_id: str
    name: str
    created_at: int
    signature: str

class ChannelEventData(TypedDict):
    """Channel event data structure"""
    type: Literal["channel"]
    channel_id: str
    group_id: str
    network_id: str
    creator_id: str
    name: str
    created_at: int
    signature: str

class MessageEventData(TypedDict):
    """Message event data structure"""
    type: Literal["message"]
    message_id: str
    channel_id: str
    group_id: str
    network_id: str
    peer_id: str
    content: str
    created_at: int
    signature: str

class InviteEventData(TypedDict):
    """Invite event data structure"""
    type: Literal["invite"]
    invite_id: str
    invite_pubkey: str
    group_id: str
    network_id: str
    inviter_id: str
    created_at: int
    signature: str

class UserEventData(TypedDict):
    """User event data structure"""
    type: Literal["user"]
    user_id: str
    peer_id: str
    network_id: str
    group_id: str
    name: str
    invite_pubkey: str
    invite_signature: str
    created_at: int
    signature: str

class MemberEventData(TypedDict):
    """Member event data structure (for group membership)"""
    type: Literal["member"]
    add_id: str
    group_id: str
    network_id: str
    adder_id: str
    user_id: str
    created_at: int
    signature: str

# Registry mapping event types to data classes
EVENT_TYPE_REGISTRY: dict[str, Type[Any]] = {
    "identity": IdentityEventData,
    "network": NetworkEventData,
    "key": KeyEventData,
    "transit_secret": TransitSecretEventData,
    "group": GroupEventData,
    "channel": ChannelEventData,
    "message": MessageEventData,
    "invite": InviteEventData,
    "user": UserEventData,
    "member": MemberEventData,
}

# Command parameter types using dataclasses for validation

@dataclass
class CreateIdentityParams:
    """Parameters for creating an identity"""
    name: str
    network_id: str

@dataclass
class CreateNetworkParams:
    """Parameters for creating a network"""
    name: str

@dataclass
class CreateKeyParams:
    """Parameters for creating a key"""
    network_id: str
    group_id: Optional[str] = None

@dataclass
class CreateTransitSecretParams:
    """Parameters for creating a transit secret"""
    network_id: str

@dataclass
class CreateGroupParams:
    """Parameters for creating a group"""
    name: str
    network_id: str
    identity_id: str

@dataclass
class CreateChannelParams:
    """Parameters for creating a channel"""
    name: str
    group_id: str
    identity_id: str

@dataclass
class CreateMessageParams:
    """Parameters for creating a message"""
    content: str
    channel_id: str
    identity_id: str

@dataclass
class CreateInviteParams:
    """Parameters for creating an invite"""
    invitee_id: str
    group_id: str
    identity_id: str

@dataclass
class CreateUserParams:
    """Parameters for creating a user"""
    address: str
    port: int
    network_id: str
    identity_id: str

@dataclass
class CreateMemberParams:
    """Parameters for creating a group member"""
    user_id: str
    group_id: str
    identity_id: str

# Command parameter registry
COMMAND_PARAMS_REGISTRY: dict[str, Type] = {
    "identity": CreateIdentityParams,
    "network": CreateNetworkParams,
    "key": CreateKeyParams,
    "transit_secret": CreateTransitSecretParams,
    "group": CreateGroupParams,
    "channel": CreateChannelParams,
    "message": CreateMessageParams,
    "invite": CreateInviteParams,
    "user": CreateUserParams,
    "member": CreateMemberParams,
}

def validate_event_data(event_type: str, event_data: dict) -> bool:
    """
    Validate that event data matches the expected structure.
    
    Args:
        event_type: The type of event
        event_data: The event data to validate
        
    Returns:
        True if valid, False otherwise
    """
    if event_type not in EVENT_TYPE_REGISTRY:
        return False
    
    expected_type = EVENT_TYPE_REGISTRY[event_type]
    required_fields = {k for k, v in expected_type.__annotations__.items() 
                      if not (hasattr(v, '__origin__') and v.__origin__ is Optional)}
    
    # Check all required fields are present
    for field in required_fields:
        if field not in event_data:
            return False
    
    # Check type field matches
    if event_data.get('type') != event_type:
        return False
    
    return True