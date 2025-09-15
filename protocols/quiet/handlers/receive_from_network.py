"""
Handler that processes envelopes from the network interface.
Extracts transit layer information from raw network data.
"""
import time
from typing import List, Dict, Any
import sqlite3
from core.handlers import Handler
from core.crypto import hash
from protocols.quiet.protocol_types import validate_envelope_fields, cast_envelope
# TODO: Handle imports: NetworkEnvelope, TransitEnvelope


class ReceiveFromNetworkHandler(Handler):
    """
    Processes raw network data and extracts transit layer information.
    Consumes: envelopes with origin_ip, origin_port, received_at, raw_data
    Emits: envelopes with transit_key_id and transit_ciphertext
    """
    
    @property
    def name(self) -> str:
        return "receive_from_network"
    
    def filter(self, envelope: dict[str, Any]) -> bool:
        """Process envelopes with raw network data."""
        # Validate we have NetworkEnvelope required fields
        return (
            validate_envelope_fields(envelope, {'raw_data', 'origin_ip', 'origin_port', 'received_at'}) and
            envelope.get('transit_key_id') is None  # Not yet processed
        )
    
    def process(self, envelope: dict[str, Any], db: sqlite3.Connection) -> List[dict[str, Any]]:
        """Extract transit key ID and ciphertext from raw data."""
        # Runtime validation - ensure we have required fields
        if not validate_envelope_fields(envelope, {'raw_data', 'origin_ip', 'origin_port', 'received_at'}):
            envelope['error'] = "Missing required NetworkEnvelope fields"
            return []
        
        # For now, assume raw_data format is:
        # [32 bytes transit_key_id][remaining bytes transit_ciphertext]
        raw_data = envelope['raw_data']
        if len(raw_data) < 33:
            envelope['error'] = "Raw data too short for transit layer"
            return []
        
        # Extract transit key ID (first 32 bytes)
        transit_key_id = raw_data[:32]
        transit_ciphertext = raw_data[32:]
        
        # Create new envelope with transit info
        transit_key_id_hex = transit_key_id.hex()
        new_envelope: dict[str, Any] = {
            'origin_ip': envelope['origin_ip'],
            'origin_port': envelope['origin_port'],
            'received_at': envelope['received_at'],
            'transit_key_id': transit_key_id_hex,
            'transit_ciphertext': transit_ciphertext,
            # Add deps to enable resolve_deps handler
            'deps': [f'transit_key:{transit_key_id_hex}']
        }
        
        return [new_envelope]