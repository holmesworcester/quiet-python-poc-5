"""
Handler that processes envelopes from the network interface.
Extracts transit layer information from raw network data.
"""
import time
from typing import List
import sqlite3
from core.envelope import Envelope
from core.handler import Handler
from core.crypto import hash


class ReceiveFromNetworkHandler(Handler):
    """
    Processes raw network data and extracts transit layer information.
    Consumes: envelopes with origin_ip, origin_port, received_at, raw_data
    Emits: envelopes with transit_key_id and transit_ciphertext
    """
    
    @property
    def name(self) -> str:
        return "receive_from_network"
    
    def filter(self, envelope: Envelope) -> bool:
        """Process envelopes with raw network data."""
        return (
            envelope.raw_data is not None and
            envelope.origin_ip is not None and
            envelope.transit_key_id is None  # Not yet processed
        )
    
    def process(self, envelope: Envelope, db: sqlite3.Connection) -> List[Envelope]:
        """Extract transit key ID and ciphertext from raw data."""
        
        # For now, assume raw_data format is:
        # [32 bytes transit_key_id][remaining bytes transit_ciphertext]
        if len(envelope.raw_data) < 33:
            envelope.error = "Raw data too short for transit layer"
            return []
        
        # Extract transit key ID (first 32 bytes)
        transit_key_id = envelope.raw_data[:32]
        transit_ciphertext = envelope.raw_data[32:]
        
        # Create new envelope with transit info
        new_envelope = Envelope(
            origin_ip=envelope.origin_ip,
            origin_port=envelope.origin_port,
            received_at=envelope.received_at,
            transit_key_id=transit_key_id.hex(),
            transit_ciphertext=transit_ciphertext
        )
        
        return [new_envelope]