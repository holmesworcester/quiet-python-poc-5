"""
Send to Network handler - Sends transit-encrypted envelopes to the network.

With strict typing, we no longer need strip_for_send. This handler only
accepts OutgoingTransitEnvelope which contains exactly what goes on the wire.
"""

# Removed core.types import
from protocols.quiet.protocol_types import OutgoingTransitEnvelope
from typing import Any, List, Callable, cast
import sqlite3
from core.handlers import Handler


def filter_func(envelope: dict[str, Any]) -> bool:
    """
    Process envelopes that have transit encryption and destination info.
    
    The type system ensures we only get properly formatted transit envelopes.
    """
    return (
        'transit_ciphertext' in envelope and
        'transit_key_id' in envelope and
        'dest_ip' in envelope and
        'dest_port' in envelope
    )


def handler(envelope: dict[str, Any], send_func: Callable) -> None:
    """
    Send envelope to network.
    
    Args:
        envelope: Must be OutgoingTransitEnvelope type
        send_func: Framework-provided function to send data to network
        
    Returns:
        None - this is a terminal handler
    """
    # Type check - in production this would be enforced by the type system
    required_fields = {'transit_ciphertext', 'transit_key_id', 'dest_ip', 'dest_port'}
    if not all(field in envelope for field in required_fields):
        raise TypeError(f"send_to_network requires OutgoingTransitEnvelope type with fields: {required_fields}")
    
    # Cast to strict type
    transit_envelope = cast(OutgoingTransitEnvelope, envelope)
    
    # Create raw network data: [32 bytes transit_key_id][remaining bytes transit_ciphertext]
    # This matches what receive_from_network expects
    transit_key_bytes = bytes.fromhex(transit_envelope['transit_key_id'])
    if len(transit_key_bytes) != 32:
        # Pad or truncate to 32 bytes
        transit_key_bytes = transit_key_bytes[:32].ljust(32, b'\0')
    
    raw_data = transit_key_bytes + transit_envelope['transit_ciphertext']
    
    # Send to network
    try:
        send_func(
            transit_envelope['dest_ip'],
            transit_envelope['dest_port'],
            raw_data,
            transit_envelope.get('due_ms', 0)
        )
    except Exception as e:
        # Log error but don't crash
        print(f"Failed to send to {transit_envelope['dest_ip']}:{transit_envelope['dest_port']}: {e}")
    
    # No return - this is a terminal handler

class SendToNetworkHandler(Handler):
    """Handler for send to network."""

    @property
    def name(self) -> str:
        return "send_to_network"

    def filter(self, envelope: dict[str, Any]) -> bool:
        """Check if this handler should process the envelope."""
        return filter_func(envelope)

    def process(self, envelope: dict[str, Any], db: sqlite3.Connection) -> List[dict[str, Any]]:
        """
        Terminal handler - sends to network and returns nothing.
        Note: In a real implementation, this would need access to a network send function.
        For now, we just log and return empty list.
        """
        # Type check - in production this would be enforced by the type system
        required_fields = {'transit_ciphertext', 'transit_key_id', 'dest_ip', 'dest_port'}
        if not all(field in envelope for field in required_fields):
            print(f"[send_to_network] ERROR: Missing required fields. Got: {envelope.keys()}")
            return []

        # Log what we would send
        print(f"[send_to_network] Would send to {envelope['dest_ip']}:{envelope['dest_port']}")

        # Terminal handler - no new envelopes
        return []
