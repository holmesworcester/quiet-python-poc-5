"""Core network functions and simulator helpers.

This module exposes two layers:
- Low-level helpers that operate on an explicit UDPNetworkSimulator instance
  (existing functions: send_packet, receive_packets, create_network_tick, etc.)
- A simple module-level simulator facade (new) that can be initialized and
  used via `send_raw` and `deliver_due` without passing the simulator around.

Note: The module-level simulator is provided but not automatically initialized.
Call `init_simulator(...)` explicitly to set it up. Nothing in the codebase is
wired to use this yet; it is safe to import without side effects.
"""

import sqlite3
import time
from typing import Dict, List, Any, Optional
from core.network_simulator import UDPNetworkSimulator, NetworkConfig


def send_packet(simulator: UDPNetworkSimulator, envelope: Dict[str, Any],
                origin_ip: Optional[str] = None, origin_port: int = 5000) -> List[Dict[str, Any]]:
    """
    Send a packet through the network simulator.

    This function is called by SendToNetworkHandler to send packets.

    Args:
        simulator: The network simulator instance
        envelope: Envelope from SendToNetworkHandler containing:
            - dest_ip: Destination IP address
            - dest_port: Destination port
            - transit_ciphertext: Encrypted payload
            - transit_key_id: Transit key ID (for reference)
            - due_ms: Optional send time
        origin_ip: Source IP address (defaults to localhost)
        origin_port: Source port (defaults to 5000)

    Returns:
        Empty list (packets are queued for later delivery)
    """
    # Extract fields from envelope
    dest_ip = envelope.get('dest_ip')
    dest_port = envelope.get('dest_port', 5000)
    transit_ciphertext = envelope.get('transit_ciphertext')
    transit_key_id = envelope.get('transit_key_id')

    if not dest_ip or not transit_ciphertext:
        return []

    # Use provided origin or defaults
    if origin_ip is None:
        origin_ip = '127.0.0.1'  # Default to localhost

    # Construct raw data: 32-byte transit key ID + ciphertext
    # This matches what ReceiveFromNetworkHandler expects
    if transit_key_id:
        transit_key_bytes = bytes.fromhex(transit_key_id)
        # Ensure exactly 32 bytes
        transit_key_bytes = transit_key_bytes[:32].ljust(32, b'\0')
    else:
        # Extract from ciphertext if not provided separately
        transit_key_bytes = transit_ciphertext[:32]
        transit_ciphertext = transit_ciphertext[32:]

    raw_data = transit_key_bytes + transit_ciphertext

    # Get current time or use due_ms if provided
    current_time_ms = envelope.get('due_ms')
    if current_time_ms is None:
        current_time_ms = int(time.time() * 1000)

    # Send through simulator
    simulator.send(
        origin_ip=origin_ip,
        origin_port=origin_port,
        dest_ip=dest_ip,
        dest_port=dest_port,
        data=raw_data,
        current_time_ms=current_time_ms
    )

    # Return empty list - packets are queued for delivery
    return []


def receive_packets(simulator: UDPNetworkSimulator,
                   current_time_ms: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Receive packets from the network simulator.

    This function is called periodically to check for incoming packets.

    Args:
        simulator: The network simulator instance
        current_time_ms: Current time in milliseconds (defaults to wall clock)

    Returns:
        List of envelopes ready for ReceiveFromNetworkHandler:
        - raw_data: 32-byte transit key ID + ciphertext
        - origin_ip: Source IP address
        - origin_port: Source port
        - received_at: Delivery timestamp
    """
    if current_time_ms is None:
        current_time_ms = int(time.time() * 1000)

    # Get packets from simulator
    return simulator.receive(current_time_ms)


def create_network_tick(current_time_ms: Optional[int] = None) -> Dict[str, Any]:
    """
    Create a network tick envelope to trigger packet reception.

    Args:
        current_time_ms: Current time in milliseconds

    Returns:
        Envelope that triggers ReceiveFromNetworkHandler
    """
    if current_time_ms is None:
        current_time_ms = int(time.time() * 1000)

    return {
        'type': 'network_tick',
        'time_ms': current_time_ms
    }


def get_peer_addresses(db: sqlite3.Connection, peer_id: str) -> List[tuple[str, int]]:
    """
    Get active addresses for a peer from the database.

    Args:
        db: Database connection
        peer_id: ID of the peer

    Returns:
        List of (ip, port) tuples
    """
    cursor = db.cursor()
    cursor.execute("""
        SELECT ip, port
        FROM addresses
        WHERE peer_id = ? AND is_active = TRUE
    """, (peer_id,))
    return cursor.fetchall()


def register_address(db: sqlite3.Connection, peer_id: str, ip: str, port: int,
                     timestamp_ms: Optional[int] = None) -> None:
    """
    Register an address for a peer in the database.

    Args:
        db: Database connection
        peer_id: ID of the peer
        ip: IP address
        port: Port number
        timestamp_ms: Registration timestamp
    """
    if timestamp_ms is None:
        timestamp_ms = int(time.time() * 1000)

    cursor = db.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO addresses (peer_id, ip, port, registered_at_ms, is_active)
        VALUES (?, ?, ?, ?, TRUE)
    """, (peer_id, ip, port, timestamp_ms))
    db.commit()


def deregister_address(db: sqlite3.Connection, peer_id: str, ip: str, port: int) -> None:
    """
    Deregister an address for a peer.

    Args:
        db: Database connection
        peer_id: ID of the peer
        ip: IP address
        port: Port number
    """
    cursor = db.cursor()
    cursor.execute("""
        UPDATE addresses
        SET is_active = FALSE
        WHERE peer_id = ? AND ip = ? AND port = ?
    """, (peer_id, ip, port))
    db.commit()


# ----------------------------------------------------------------------------
# Module-level simulator facade (not wired by default)
# ----------------------------------------------------------------------------

_SIMULATOR: UDPNetworkSimulator | None = None


def init_simulator(config: NetworkConfig | None = None) -> None:
    """Initialize the module-level UDPNetworkSimulator instance.

    This does not hook into any handlers or APIs automatically. Callers must
    explicitly use `send_raw` and `deliver_due` (and feed deliveries into the
    pipeline) if they want to drive simulated network IO.

    Args:
        config: Optional `NetworkConfig` with loss/latency/size.
    """
    global _SIMULATOR
    _SIMULATOR = UDPNetworkSimulator(config or NetworkConfig())


def has_simulator() -> bool:
    """Return True if the module-level simulator has been initialized."""
    return _SIMULATOR is not None


def reset_simulator() -> None:
    """Drop the module-level simulator (useful for tests)."""
    global _SIMULATOR
    _SIMULATOR = None


def send_raw(dest_ip: str,
             dest_port: int,
             raw_data: bytes,
             due_ms: Optional[int] = None,
             origin_ip: str = '127.0.0.1',
             origin_port: int = 5000) -> bool:
    """Enqueue a raw packet into the module-level simulator.

    The packet should already be in the wire format that
    ReceiveFromNetworkHandler expects: 32-byte transit key id prefix + ciphertext.

    Args:
        dest_ip: Destination IP address
        dest_port: Destination port
        raw_data: Raw bytes to send (transit_key_id + transit_ciphertext)
        due_ms: Optional delivery time in ms (defaults to simulator time + latency)
        origin_ip: Source IP (defaults to localhost)
        origin_port: Source port

    Returns:
        True if queued (not dropped), False if dropped by simulator.

    Raises:
        RuntimeError: If the simulator has not been initialized.
    """
    if _SIMULATOR is None:
        raise RuntimeError("Simulator not initialized. Call init_simulator() first.")

    return _SIMULATOR.send(
        origin_ip=origin_ip,
        origin_port=origin_port,
        dest_ip=dest_ip,
        dest_port=dest_port,
        data=raw_data,
        current_time_ms=due_ms,
    )


def deliver_due(current_time_ms: Optional[int] = None) -> List[Dict[str, Any]]:
    """Deliver due packets from the module-level simulator.

    Returns envelopes suitable for input to ReceiveFromNetworkHandler, with
    fields: raw_data, origin_ip, origin_port, received_at. Destination fields
    are included for debugging:
    - dest_ip, dest_port (as sent)
    - received_by_ip, received_by_port (same as dest_* for clarity)

    Args:
        current_time_ms: Optional time reference in milliseconds. If not
                         provided, the simulator's internal time is used.

    Returns:
        List of network input envelopes for the pipeline.

    Raises:
        RuntimeError: If the simulator has not been initialized.
    """
    if _SIMULATOR is None:
        raise RuntimeError("Simulator not initialized. Call init_simulator() first.")

    packets = _SIMULATOR.receive(current_time_ms)
    # Packets already come in envelope-like dicts from the simulator. Augment
    # with 'received_by_*' for clarity; keep dest_* for debugging.
    enriched: List[Dict[str, Any]] = []
    for pkt in packets:
        env = dict(pkt)
        env['received_by_ip'] = pkt.get('dest_ip')
        env['received_by_port'] = pkt.get('dest_port')
        enriched.append(env)
    return enriched
