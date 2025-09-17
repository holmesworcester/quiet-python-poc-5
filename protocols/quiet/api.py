"""
Explicit API surface for the Quiet protocol.

This file declares which operations are exposed and how they are fulfilled:
- 'flow'   => a registered @flow_op function
- 'query'  => a query in query registry

Only operations listed here (plus 'core.*') are callable via API.
"""

EXPOSED: dict[str, str] = {
    # Flows
    'user.join_as_user': 'flow',
    'peer.create': 'flow',
    'network.create': 'flow',
    'group.create': 'flow',
    'channel.create': 'flow',
    'message.create': 'flow',
    'invite.create': 'flow',
    'address.announce': 'flow',
    'identity.create_as_user': 'flow',
    'sync_request.run': 'flow',

    # Former commands converted to flows
    'user.create': 'flow',
    'identity.create': 'flow',

    # Queries
    'message.get': 'query',
    'user.get': 'query',
}

# No aliases: prefer natural names directly
