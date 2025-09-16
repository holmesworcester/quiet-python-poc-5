"""
Typed client helpers for the Quiet protocol.

These wrappers provide simple, mypy-checkable interfaces over API.execute_operation
so call sites get param/result type safety without needing OpenAPI schemas.
"""
from __future__ import annotations

from typing import Any, Dict, List, TypedDict, Optional, cast
from typing_extensions import NotRequired

from typing import TYPE_CHECKING
if TYPE_CHECKING:  # Avoid runtime import cycles
    from core.api import API


# =========================
# Common response envelopes
# =========================

class CommandIds(TypedDict, total=False):
    identity: str
    peer: str
    network: str
    group: str
    channel: str
    message: str
    invite: str
    user: str
    address: str
    link_invite: str


class CommandResponse(TypedDict):
    ids: CommandIds
    data: Dict[str, Any]


# ============
# Core: identity
# ============

class CreateIdentityParams(TypedDict):
    name: NotRequired[str]


class CoreIdentity(TypedDict):
    identity_id: str
    name: str
    public_key: str
    created_at: NotRequired[int]


class CreateIdentityResult(TypedDict):
    ids: Dict[str, str]  # {'identity': id}
    data: CoreIdentity


def core_identity_create(api: 'API', params: CreateIdentityParams) -> CreateIdentityResult:
    return cast(CreateIdentityResult, api.execute_operation('core.identity_create', cast(Dict[str, Any], params)))


class IdentityListResult(TypedDict):
    data: Dict[str, List[CoreIdentity]]  # {'identities': [...]}


def core_identity_list(api: 'API') -> IdentityListResult:
    return cast(IdentityListResult, api.execute_operation('core.identity_list', {}))


# ======
# Peer
# ======

class CreatePeerParams(TypedDict):
    identity_id: str
    username: NotRequired[str]


def create_peer(api: 'API', params: CreatePeerParams) -> CommandResponse:
    return cast(CommandResponse, api.execute_operation('peer.create_peer', cast(Dict[str, Any], params)))


# ==========
# Address
# ==========

class AnnounceAddressParams(TypedDict):
    peer_id: str
    ip: str
    port: int
    network_id: NotRequired[str]
    action: NotRequired[str]


def announce_address(api: 'API', params: AnnounceAddressParams) -> CommandResponse:
    return cast(CommandResponse, api.execute_operation('address.announce_address', cast(Dict[str, Any], params)))


# =========
# Network
# =========

class CreateNetworkParams(TypedDict):
    name: str
    peer_id: NotRequired[str]
    identity_id: NotRequired[str]


def create_network(api: 'API', params: CreateNetworkParams) -> CommandResponse:
    return cast(CommandResponse, api.execute_operation('network.create_network', cast(Dict[str, Any], params)))


class NetworkRecord(TypedDict, total=False):
    network_id: str
    name: str
    creator_id: str
    created_at: int


class NetworkGetParams(TypedDict, total=False):
    network_id: str
    peer_id: str


def network_get(api: 'API', params: NetworkGetParams) -> List[NetworkRecord]:
    return cast(List[NetworkRecord], api.execute_operation('network.get', cast(Dict[str, Any], params)))


# ======
# Group
# ======

class CreateGroupParams(TypedDict):
    name: str
    network_id: str
    peer_id: str


class GroupRecord(TypedDict, total=False):
    group_id: str
    name: str
    creator_id: str
    network_id: NotRequired[str]
    created_at: NotRequired[int]
    member_count: NotRequired[int]


class CreateGroupData(TypedDict):
    group_id: str
    name: str
    network_id: str
    creator_id: str
    groups: List[GroupRecord]


class CreateGroupResult(TypedDict):
    ids: CommandIds
    data: CreateGroupData


def create_group(api: 'API', params: CreateGroupParams) -> CreateGroupResult:
    return cast(CreateGroupResult, api.execute_operation('group.create_group', cast(Dict[str, Any], params)))


class GroupGetParams(TypedDict, total=False):
    identity_id: str
    network_id: NotRequired[str]
    user_id: NotRequired[str]


def group_get(api: 'API', params: GroupGetParams) -> List[GroupRecord]:
    return cast(List[GroupRecord], api.execute_operation('group.get', cast(Dict[str, Any], params)))


# =========
# Channel
# =========

class CreateChannelParams(TypedDict):
    name: str
    group_id: str
    peer_id: str
    network_id: str


class ChannelRecord(TypedDict, total=False):
    channel_id: str
    name: str
    group_id: str
    network_id: NotRequired[str]
    created_at: NotRequired[int]


class CreateChannelData(TypedDict):
    channel_id: str
    name: str
    group_id: str
    channels: List[ChannelRecord]


class CreateChannelResult(TypedDict):
    ids: CommandIds
    data: CreateChannelData


def create_channel(api: 'API', params: CreateChannelParams) -> CreateChannelResult:
    return cast(CreateChannelResult, api.execute_operation('channel.create_channel', cast(Dict[str, Any], params)))


class ChannelGetParams(TypedDict, total=False):
    identity_id: str
    group_id: NotRequired[str]
    network_id: NotRequired[str]


def channel_get(api: 'API', params: ChannelGetParams) -> List[ChannelRecord]:
    return cast(List[ChannelRecord], api.execute_operation('channel.get', cast(Dict[str, Any], params)))


# =========
# Message
# =========

class CreateMessageParams(TypedDict):
    content: str
    channel_id: str
    peer_id: str


class MessageRecord(TypedDict, total=False):
    message_id: str
    content: str
    channel_id: str
    author_id: NotRequired[str]
    created_at: NotRequired[int]
    author_name: NotRequired[str]


class CreateMessageData(TypedDict):
    message_id: str
    channel_id: str
    content: str
    messages: List[MessageRecord]


class CreateMessageResult(TypedDict):
    ids: CommandIds
    data: CreateMessageData


def create_message(api: 'API', params: CreateMessageParams) -> CreateMessageResult:
    return cast(CreateMessageResult, api.execute_operation('message.create_message', cast(Dict[str, Any], params)))


class MessageGetParams(TypedDict, total=False):
    identity_id: str
    channel_id: NotRequired[str]
    group_id: NotRequired[str]
    limit: NotRequired[int]
    offset: NotRequired[int]


def message_get(api: 'API', params: MessageGetParams) -> List[MessageRecord]:
    return cast(List[MessageRecord], api.execute_operation('message.get', cast(Dict[str, Any], params)))


# ======
# Invite
# ======

class CreateInviteParams(TypedDict):
    network_id: str
    group_id: str
    peer_id: str


class CreateInviteResultData(TypedDict, total=False):
    invite_link: str
    invite_code: str
    invite_id: str
    network_id: str
    group_id: str


class CreateInviteResult(TypedDict):
    ids: CommandIds
    data: CreateInviteResultData


def create_invite(api: 'API', params: CreateInviteParams) -> CreateInviteResult:
    return cast(CreateInviteResult, api.execute_operation('invite.create_invite', cast(Dict[str, Any], params)))


# =====
# User
# =====

class JoinAsUserParams(TypedDict):
    invite_link: str
    name: NotRequired[str]


class JoinData(TypedDict):
    name: str
    joined: bool


class JoinAsUserResult(TypedDict):
    ids: CommandIds
    data: JoinData


def join_as_user(api: 'API', params: JoinAsUserParams) -> JoinAsUserResult:
    return cast(JoinAsUserResult, api.execute_operation('user.join_as_user', cast(Dict[str, Any], params)))


class UserRecord(TypedDict, total=False):
    user_id: str
    peer_id: str
    network_id: str
    name: NotRequired[str]
    joined_at: NotRequired[int]


class UserGetParams(TypedDict):
    identity_id: str
    network_id: str
    limit: NotRequired[int]
    offset: NotRequired[int]


def user_get(api: 'API', params: UserGetParams) -> List[UserRecord]:
    return cast(List[UserRecord], api.execute_operation('user.get', cast(Dict[str, Any], params)))


class CreateUserParams(TypedDict, total=False):
    peer_id: str
    network_id: str
    name: str
    group_id: str


def create_user(api: 'API', params: CreateUserParams) -> CommandResponse:
    return cast(CommandResponse, api.execute_operation('user.create_user', cast(Dict[str, Any], params)))


# ======
# Keys
# ======

class KeyRecord(TypedDict, total=False):
    key_id: str
    group_id: str
    peer_id: str
    created_at: int


class KeyListParams(TypedDict, total=False):
    group_id: str


def key_list(api: 'API', params: Optional[KeyListParams] = None) -> List[KeyRecord]:
    return cast(List[KeyRecord], api.execute_operation('key.list', cast(Dict[str, Any], params or {})))


class CreateKeyParams(TypedDict):
    group_id: str
    network_id: str
    identity_id: str


def create_key(api: 'API', params: CreateKeyParams) -> CommandResponse:
    return cast(CommandResponse, api.execute_operation('key.create_key', cast(Dict[str, Any], params)))


# ==================
# Transit keys (list)
# ==================

class TransitKeyRecord(TypedDict, total=False):
    transit_key_id: str
    peer_id: str
    network_id: str
    created_at: int


class TransitKeyListParams(TypedDict, total=False):
    network_id: str


def transit_key_list(api: 'API', params: Optional[TransitKeyListParams] = None) -> List[TransitKeyRecord]:
    return cast(List[TransitKeyRecord], api.execute_operation('transit_secret.list', cast(Dict[str, Any], params or {})))


class CreateTransitSecretParams(TypedDict):
    network_id: str
    identity_id: str


def create_transit_secret(api: 'API', params: CreateTransitSecretParams) -> CommandResponse:
    return cast(CommandResponse, api.execute_operation('transit_secret.create_transit_secret', cast(Dict[str, Any], params)))


# ======
# Link Invite
# ======

class CreateLinkInviteParams(TypedDict):
    peer_id: str
    user_id: str
    network_id: str


def create_link_invite(api: 'API', params: CreateLinkInviteParams) -> CommandResponse:
    return cast(CommandResponse, api.execute_operation('link_invite.create_link_invite', cast(Dict[str, Any], params)))


# ======
# Member
# ======

class MemberRecord(TypedDict, total=False):
    user_id: str
    name: NotRequired[str]
    peer_id: NotRequired[str]
    created_at: NotRequired[int]


class CreateMemberParams(TypedDict):
    group_id: str
    user_id: str
    identity_id: str
    network_id: str


class CreateMemberResult(TypedDict):
    added: bool
    group_id: str
    members: List[MemberRecord]
    member_count: int


def create_member(api: 'API', params: CreateMemberParams) -> CreateMemberResult:
    return cast(CreateMemberResult, api.execute_operation('member.create_member', cast(Dict[str, Any], params)))
