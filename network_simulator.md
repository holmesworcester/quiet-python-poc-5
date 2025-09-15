# UDP Network Simulator Design

## Overview
A UDP network simulator that operates as part of the envelope processing pipeline, simulating realistic network conditions including packet loss, latency, and size constraints.

## Key Features
- **Packet Size Limit**: Drops packets over 600 bytes (configurable)
- **Packet Loss**: Configurable loss rate (0.0 to 1.0)
- **Latency**: Configurable delay in milliseconds
- **No Address Validation**: Simulator delivers all packets that pass physical constraints (size/loss). Address validation happens at the application layer (handlers check if they should process the packet)
- **Time Simulation**: Controlled time advancement for deterministic testing

## Architecture

### Core Components

#### 1. Network Simulator Module (`core/network_simulator.py`)
- `UDPNetworkSimulator` class managing packet routing and timing
- `NetworkConfig` dataclass for configuration
- `PendingPacket` dataclass for queued packets
- **Core-level `send()` and `receive()` functions** that can be called directly by handlers or tests
- `receive()` outputs envelopes that match `ReceiveFromNetworkHandler`'s filter (with `raw_data`, `origin_ip`, etc.)
- The simulator itself is protocol-agnostic and lives entirely in core

#### 2. Address Event Type (`protocols/quiet/events/address/`)
- Commands to create address registration/deregistration events
- Validator for address format and uniqueness
- Projector to maintain peer address mappings in the database
- **Note**: Network routing is based on transit-encryption keys matching network-ids, not IP addresses

#### 3. Core Network Functions (`core/network.py`)
- `send_packet(simulator, envelope)`: Core function to send via simulator
- `receive_packets(simulator, current_time_ms)`: Core function to emit pending packets into pipeline
- Envelopes contain all necessary routing information

## Data Flow

### Sending Process
1. `SendToNetworkHandler` calls `send_packet(envelope)` with:
   - `dest_ip` and `dest_port`: Destination address
   - `transit_ciphertext`: Encrypted payload with transit key ID prefix
   - `due_ms`: Optional send time

2. Network simulator:
   - Checks packet size (drops if > 600B)
   - Applies packet loss (random drop based on configured rate)
   - Calculates delivery time: `current_time + latency_ms`
   - Queues packet for delivery

### Receiving Process
1. Pipeline periodically calls `receive_packets(current_time_ms)`
2. Simulator returns packets due for delivery as envelopes with:
   - `raw_data`: Transit key ID (32 bytes) + ciphertext
   - `origin_ip`: Source IP address
   - `origin_port`: Source port
   - `received_at`: Delivery timestamp in ms
3. These envelopes match `ReceiveFromNetworkHandler`'s filter
4. Handler extracts transit key and processes normally

## Envelope Fields

### Input to send_packet (from SendToNetworkHandler)
```python
{
    'dest_ip': '192.168.1.101',
    'dest_port': 5000,
    'transit_ciphertext': b'...',  # Already includes transit key ID
    'transit_key_id': 'abc123...',  # For reference
    'due_ms': 1234567890  # Optional
}
```

### Output from receive_packets (to ReceiveFromNetworkHandler)
```python
{
    'raw_data': b'...',  # 32-byte transit key ID + ciphertext
    'origin_ip': '192.168.1.100',
    'origin_port': 5000,
    'received_at': 1234567950  # Delivery timestamp
}
```

## Address Management

### Address Event Structure
```python
{
    'event_type': 'address',
    'action': 'add' | 'remove',
    'peer_id': 'peer_123',  # ID of the peer advertising this address
    'ip': '192.168.1.100',
    'port': 5000,
    'timestamp_ms': 1234567890
}
```

### Address Registration Flow
1. Peer creates address event with action='add' using their peer_id
2. Event is validated and projected to database
3. Addresses are used for routing decisions at application layer

### Simplified Packet Delivery
The simulator doesn't validate addresses - it's just a dumb pipe:
1. Simulator delivers ALL packets that pass physical constraints (size/loss/latency)
2. Creates receive envelopes with `raw_data` containing transit key + ciphertext
3. `ReceiveFromNetworkHandler` extracts transit key ID
4. Pipeline uses transit key to determine if packet is for us (key matching network-id)
5. Packets with unknown transit keys are naturally dropped by the pipeline

This matches real UDP behavior - the network delivers everything, applications decide what to process.

## Database Schema

### Address Table
```sql
CREATE TABLE IF NOT EXISTS addresses (
    peer_id TEXT NOT NULL,
    ip TEXT NOT NULL,
    port INTEGER NOT NULL,
    registered_at_ms INTEGER NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    PRIMARY KEY (peer_id, ip, port)
);
```

## Integration with Existing Handlers

### Using Existing Send/Receive Handlers
We already have `SendToNetworkHandler` and `ReceiveFromNetworkHandler` - let's integrate the simulator with them:

```python
# In SendToNetworkHandler - instead of calling send_func directly
class SendToNetworkHandler(Handler):
    def __init__(self, simulator: UDPNetworkSimulator):
        self.simulator = simulator

    def process(self, envelope: dict, db: sqlite3.Connection) -> List[dict]:
        # Existing validation...

        # Convert to simulator send envelope
        send_envelope = {
            'is_send': True,
            'origin_ip': get_my_ip(db),  # Look up our address
            'send_to': [(envelope['dest_ip'], envelope['dest_port'])],
            'sent_at_ms': int(time.time() * 1000),
            'transit_ciphertext': envelope['transit_ciphertext'],
            'transit_key_id': envelope['transit_key_id']
        }

        # Use simulator instead of direct network
        return self.simulator.send_packet(send_envelope)

# In ReceiveFromNetworkHandler - gets packets from simulator
class ReceiveFromNetworkHandler(Handler):
    def __init__(self, simulator: UDPNetworkSimulator):
        self.simulator = simulator

    def filter(self, envelope: dict) -> bool:
        # Process network tick events to check for incoming packets
        return envelope.get('type') == 'network_tick'

    def process(self, envelope: dict, db: sqlite3.Connection) -> List[dict]:
        current_time_ms = envelope.get('time_ms', int(time.time() * 1000))
        received = self.simulator.receive_packets(current_time_ms)

        # Convert simulator packets to existing format
        results = []
        for packet in received:
            # Reconstruct raw_data format expected by handler
            transit_key_bytes = bytes.fromhex(packet['transit_key_id'])
            raw_data = transit_key_bytes + packet['transit_ciphertext']

            results.append({
                'origin_ip': packet['origin_ip'],
                'origin_port': 5000,  # Default port
                'received_at': packet['received_at_ms'],
                'raw_data': raw_data
            })
        return results
```

### Pipeline Position
- **Send path**: `SendToNetworkHandler` uses simulator instead of real network
- **Receive path**: `ReceiveFromNetworkHandler` pulls from simulator on network ticks
- No new handlers needed - just modify existing ones to use simulator

## Time Management

### Simulation Modes

#### 1. Real-time Mode (Production)
- Uses actual system time
- Delivers packets based on wall clock

#### 2. Simulated Time Mode (Testing)
- Controlled time advancement
- Deterministic packet delivery
- Useful for integration tests

### Time Advancement
```python
# Advance time by 100ms and get delivered packets
delivered = simulator.advance_time(100)

# Or check for packets at specific time
delivered = simulator.receive_packets(current_time_ms=1234567890)
```

## Configuration

### NetworkConfig Options
```python
config = NetworkConfig(
    packet_loss_rate=0.05,  # 5% packet loss
    latency_ms=50,           # 50ms latency
    max_packet_size=600      # 600 byte limit
)
```

### Environment-based Config
- Development: No loss, low latency (5ms)
- Testing: Variable loss (0-20%), medium latency (20-100ms)
- Production simulation: Realistic loss (1-5%), variable latency (10-200ms)

## Testing Strategy

### Unit Tests
1. Packet size enforcement
2. Packet loss application
3. Latency calculation
4. Address registration/lookup
5. Time advancement

### Integration Tests
1. End-to-end message delivery
2. Multi-hop routing
3. Concurrent sender/receiver scenarios
4. Network partition simulation
5. Address changes during communication

### Test Utilities
```python
def create_test_network(peers: int, loss_rate: float = 0.0) -> UDPNetworkSimulator:
    """Create a test network with registered peers."""

def simulate_partition(simulator: UDPNetworkSimulator, group1: List[str], group2: List[str]):
    """Simulate network partition between two groups."""

def measure_delivery_rate(simulator: UDPNetworkSimulator, packets: int) -> float:
    """Measure actual packet delivery rate."""
```

## Implementation Phases

### Phase 1: Core Simulator and Functions
- [x] Basic simulator class in `core/network_simulator.py`
- [ ] Core network functions in `core/network.py`
- [ ] Packet queuing and delivery
- [ ] Size and loss simulation
- [ ] Time management

### Phase 2: Address Management
- [ ] Address event type in `protocols/quiet/events/address/`
- [ ] Address validation and projection
- [ ] Database schema for addresses table
- [ ] Core functions query DB for address lookups

### Phase 3: Handler Updates
- [ ] Update existing send/receive handlers to use core functions
- [ ] Pipeline integration
- [ ] Send/receive envelope conversion
- [ ] Handler tests

### Phase 4: Advanced Features
- [ ] Bandwidth limiting
- [ ] Packet reordering
- [ ] Jitter simulation
- [ ] Network topology (routing tables)

## Future Enhancements

1. **Bandwidth Limiting**: Enforce maximum throughput
2. **Packet Reordering**: Simulate out-of-order delivery
3. **Jitter**: Variable latency within ranges
4. **Network Topology**: Define network graphs with routing
5. **Congestion Simulation**: Dynamic loss based on traffic
6. **MTU Fragmentation**: Handle larger packets with fragmentation
7. **NAT Simulation**: Address translation and traversal

## Example Usage

```python
from core.network_simulator import UDPNetworkSimulator, NetworkConfig
from core.network import send_packet, receive_packets

# Create simulator with realistic conditions
simulator = UDPNetworkSimulator(NetworkConfig(
    packet_loss_rate=0.02,
    latency_ms=30,
    max_packet_size=600
))

# In practice, addresses are registered via address events in the database
# The simulator queries the DB, it doesn't store addresses itself

# Send a packet using core function
send_envelope = Envelope({
    'is_send': True,
    'origin_ip': '192.168.1.100',
    'send_to': [('192.168.1.101', 5000)],
    'sent_at_ms': 1000,
    'event_ciphertext': b'Hello Bob!',
    'event_type': 'message'
})

# Core function handles DB lookup and simulator interaction
immediate = send_packet(db, simulator, send_envelope)

# Advance time and receive packets
current_time_ms = 1050  # 50ms later
received = receive_packets(db, simulator, current_time_ms)
```