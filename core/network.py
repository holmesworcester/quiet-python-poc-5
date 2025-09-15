"""Core network functions for integrating the simulator with handlers."""

import sqlite3
import time
from typing import Dict, List, Any, Optional
from core.network_simulator import UDPNetworkSimulator


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