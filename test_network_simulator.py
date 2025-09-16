"""Test the UDP network simulator."""

import time
from core.network_simulator import UDPNetworkSimulator, NetworkConfig


def test_basic_send_receive() -> None:
    """Test basic packet send and receive."""
    # Create simulator with no loss, no latency
    config = NetworkConfig(packet_loss_rate=0.0, latency_ms=0)
    sim = UDPNetworkSimulator(config)

    # Send a packet
    data = b"Hello, World!"
    sent = sim.send(
        origin_ip="192.168.1.100",
        origin_port=5000,
        dest_ip="192.168.1.101",
        dest_port=5000,
        data=data,
        current_time_ms=1000
    )
    assert sent is True, "Packet should be queued"

    # Receive immediately (no latency)
    packets = sim.receive(current_time_ms=1000)
    assert len(packets) == 1, "Should receive one packet"

    packet = packets[0]
    assert packet['raw_data'] == data
    assert packet['origin_ip'] == "192.168.1.100"
    assert packet['origin_port'] == 5000
    assert packet['dest_ip'] == "192.168.1.101"
    assert packet['dest_port'] == 5000
    assert packet['received_at'] == 1000

    print("✓ Basic send/receive works")


def test_packet_latency() -> None:
    """Test packet latency simulation."""
    # Create simulator with 50ms latency
    config = NetworkConfig(packet_loss_rate=0.0, latency_ms=50)
    sim = UDPNetworkSimulator(config)

    # Send a packet at time 1000
    data = b"Delayed packet"
    sim.send(
        origin_ip="192.168.1.100",
        origin_port=5000,
        dest_ip="192.168.1.101",
        dest_port=5000,
        data=data,
        current_time_ms=1000
    )

    # Try to receive immediately - should get nothing
    packets = sim.receive(current_time_ms=1000)
    assert len(packets) == 0, "No packets should be ready yet"

    # Try to receive at time 1025 - still nothing
    packets = sim.receive(current_time_ms=1025)
    assert len(packets) == 0, "No packets should be ready at 25ms"

    # Receive at time 1050 - should get the packet
    packets = sim.receive(current_time_ms=1050)
    assert len(packets) == 1, "Packet should be ready at 50ms"
    assert packets[0]['received_at'] == 1050

    print("✓ Latency simulation works")


def test_packet_size_limit() -> None:
    """Test packet size enforcement."""
    # Create simulator with 100 byte limit
    config = NetworkConfig(packet_loss_rate=0.0, latency_ms=0, max_packet_size=100)
    sim = UDPNetworkSimulator(config)

    # Send a small packet - should work
    small_data = b"Small"
    sent = sim.send(
        origin_ip="192.168.1.100",
        origin_port=5000,
        dest_ip="192.168.1.101",
        dest_port=5000,
        data=small_data,
        current_time_ms=1000
    )
    assert sent is True, "Small packet should be sent"

    # Send a large packet - should be dropped
    large_data = b"X" * 101
    sent = sim.send(
        origin_ip="192.168.1.100",
        origin_port=5000,
        dest_ip="192.168.1.101",
        dest_port=5000,
        data=large_data,
        current_time_ms=1000
    )
    assert sent is False, "Large packet should be dropped"

    # Receive - should only get the small packet
    packets = sim.receive(current_time_ms=1000)
    assert len(packets) == 1
    assert packets[0]['raw_data'] == small_data

    print("✓ Packet size limit works")


def test_packet_loss() -> None:
    """Test packet loss simulation."""
    # Create simulator with 50% packet loss
    config = NetworkConfig(packet_loss_rate=0.5, latency_ms=0)
    sim = UDPNetworkSimulator(config)

    # Send many packets
    sent_count = 0
    for i in range(100):
        sent = sim.send(
            origin_ip="192.168.1.100",
            origin_port=5000,
            dest_ip="192.168.1.101",
            dest_port=5000,
            data=f"Packet {i}".encode(),
            current_time_ms=1000
        )
        if sent:
            sent_count += 1

    # With 50% loss rate, we should have roughly 50 packets queued
    # Allow for some variance (40-60)
    assert 40 <= sent_count <= 60, f"Expected ~50 packets, got {sent_count}"

    # Receive and count
    packets = sim.receive(current_time_ms=1000)
    assert len(packets) == sent_count

    print(f"✓ Packet loss works (sent {sent_count}/100)")


def test_multiple_destinations() -> None:
    """Test sending to multiple destinations."""
    config = NetworkConfig(packet_loss_rate=0.0, latency_ms=10)
    sim = UDPNetworkSimulator(config)

    # Send packets to different destinations
    destinations = [
        ("192.168.1.101", 5000),
        ("192.168.1.102", 5001),
        ("192.168.1.103", 5002),
    ]

    for i, (dest_ip, dest_port) in enumerate(destinations):
        sim.send(
            origin_ip="192.168.1.100",
            origin_port=5000,
            dest_ip=dest_ip,
            dest_port=dest_port,
            data=f"Packet {i}".encode(),
            current_time_ms=1000
        )

    # Advance time and receive all packets
    packets = sim.receive(current_time_ms=1010)
    assert len(packets) == 3, "Should receive all 3 packets"

    # Check each packet has correct destination
    received_dests = {(p['dest_ip'], p['dest_port']) for p in packets}
    assert received_dests == set(destinations)

    print("✓ Multiple destinations work")


def test_time_advancement() -> None:
    """Test the advance_time helper."""
    config = NetworkConfig(packet_loss_rate=0.0, latency_ms=30)
    sim = UDPNetworkSimulator(config)

    # Send packet at time 0
    sim.current_time_ms = 0
    sim.send(
        origin_ip="192.168.1.100",
        origin_port=5000,
        dest_ip="192.168.1.101",
        dest_port=5000,
        data=b"Test",
        current_time_ms=0
    )

    # Advance time by 20ms - no packets yet
    packets = sim.advance_time(20)
    assert len(packets) == 0
    assert sim.current_time_ms == 20

    # Advance by another 10ms - packet should arrive
    packets = sim.advance_time(10)
    assert len(packets) == 1
    assert sim.current_time_ms == 30

    print("✓ Time advancement works")


def test_transit_key_format() -> None:
    """Test that data format matches what ReceiveFromNetworkHandler expects."""
    config = NetworkConfig(packet_loss_rate=0.0, latency_ms=0)
    sim = UDPNetworkSimulator(config)

    # Simulate the format: 32-byte transit key + ciphertext
    transit_key = b"K" * 32
    ciphertext = b"encrypted data"
    raw_data = transit_key + ciphertext

    sim.send(
        origin_ip="192.168.1.100",
        origin_port=5000,
        dest_ip="192.168.1.101",
        dest_port=5000,
        data=raw_data,
        current_time_ms=1000
    )

    packets = sim.receive(current_time_ms=1000)
    assert len(packets) == 1

    packet = packets[0]
    assert packet['raw_data'] == raw_data
    # ReceiveFromNetworkHandler will extract:
    extracted_key = packet['raw_data'][:32]
    extracted_ciphertext = packet['raw_data'][32:]
    assert extracted_key == transit_key
    assert extracted_ciphertext == ciphertext

    print("✓ Transit key format correct")


if __name__ == "__main__":
    test_basic_send_receive()
    test_packet_latency()
    test_packet_size_limit()
    test_packet_loss()
    test_multiple_destinations()
    test_time_advancement()
    test_transit_key_format()
    print("\n✅ All network simulator tests passed!")
