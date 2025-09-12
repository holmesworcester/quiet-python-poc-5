# POC-3 Signed Groups Demo Analysis

## Overview
The POC-3 `signed_groups` demo is a comprehensive demonstration of a group messaging protocol with identity management, network creation, and group-based access control.

## Architecture
- **Unified CLI/TUI Implementation**: Single codebase with business logic in `SignedGroupsCore` that supports both CLI and TUI modes
- **API-Based**: Uses `APIClient` to interact with the protocol through HTTP API calls
- **Multi-Panel Design**: Supports 4 concurrent identity panels for testing multi-user scenarios

## Core Features

### 1. Identity Management
- **Create Identity**: `/create <name>` - Creates a new identity with a name
- **Panel-based**: Each panel (1-4) can have one identity
- **Auto-selection**: When creating an identity, it's automatically selected in that panel

### 2. Network Management  
- **Create Network**: `/network <name>` - Creates a new network with a default channel
- **Network Creator**: The identity creating the network becomes the first user
- **Default Channel**: Networks are created with a default "general" channel

### 3. Invitations System
- **Generate Invite**: `/invite` - Generates an invite link for the current network
- **Join Network**: `/join <invite_link>` - Join a network using an invite code
- **Automatic Access**: Joining grants access to default channels in the inviter's groups

### 4. Groups and Channels
- **Create Group**: `/group <name>` - Create a new group within a network
- **Create Channel**: `/channel <name> [in <group>]` - Create channel in a group
- **Add Users**: `/add <user> to <group>` - Add users to groups
- **Access Control**: Users can only see channels in groups they belong to

### 5. Messaging
- **Send Messages**: Type text without a slash to send to current channel
- **Channel Context**: Messages are sent to the currently selected channel
- **Message History**: Each panel maintains its own message history

## UI Features (TUI Mode)

### Panel Layout (3x2 Grid):
```
+----------------+----------------+------------------+
| Panel 1        | Panel 2        | State Inspector  |
| - Identity     | - Identity     | - Database stats |
| - Channels     | - Channels     | - Table counts   |
| - Messages     | - Messages     |                  |
+----------------+----------------+------------------+
| Panel 3        | Panel 4        | Event Log        |
| - Identity     | - Identity     | - Commands       |
| - Channels     | - Channels     | - Protocol events|
| - Messages     | - Messages     |                  |
+----------------+----------------+------------------+
```

### Channel Sidebar
Each panel includes:
- **Channels**: Grouped by group membership, clickable to switch
- **People**: List of users in the network
- **Groups**: Groups and their members

## CLI Features

### Command Format
- Panel commands: `<panel>:<command>` (e.g., `1:/create alice`)
- Variable capture: `<command> -> <var>` (e.g., `1:/invite -> link`)
- Variable substitution: `$var` or `${var}` in commands

### Script Execution
- `--run` flag for single commands
- `--script-file` for batch execution
- `--format json` for JSON output

## Key Protocol Concepts
1. **Group-based Access**: Channels exist within groups, not globally
2. **Invitation System**: Network access requires invites
3. **Multi-Identity Testing**: Designed for testing protocol interactions
4. **Event Sourcing**: All state changes tracked as events