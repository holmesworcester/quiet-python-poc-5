"""
Central commands module for Quiet protocol.
Imports all command modules to ensure they're registered.
"""

# Import all command modules to trigger registration
from .events.identity import commands as identity_commands
from .events.network import commands as network_commands
from .events.user import commands as user_commands
from .events.group import commands as group_commands
from .events.channel import commands as channel_commands
from .events.message import commands as message_commands
from .events.invite import commands as invite_commands
from .events.add import commands as add_commands
from .events.key import commands as key_commands
from .events.transit_secret import commands as transit_secret_commands
from .events.peer import commands as peer_commands
from .events.link_invite import commands as link_invite_commands
from .events.address import commands as address_commands
from .events.sync_request import commands as sync_request_commands

def register_commands():
    """Function called by pipeline to ensure commands are registered."""
    # Commands are registered via decorators when imported above
    pass