"""
Handler that decrypts transit layer encryption.
"""
import json
from typing import List, Dict, Any
import sqlite3
from core.handler import Handler
from core.crypto import decrypt, hash
from core.types import Envelope, TransitEnvelope, validate_envelope_fields, cast_envelope


class DecryptTransitHandler(Handler):
    """
    Decrypts transit layer encryption using transit keys.
    Consumes: envelopes with deps_included_and_valid, transit_key_id, transit_ciphertext
    Emits: envelopes with transit_plaintext, network_id, event_key_id, event_ciphertext, event_id
    """
    
    @property
    def name(self) -> str:
        return "decrypt_transit"
    
    def filter(self, envelope: Envelope) -> bool:
        """Process envelopes ready for transit decryption."""
        return (
            validate_envelope_fields(envelope, {'transit_key_id', 'transit_ciphertext'}) and
            envelope.get('transit_plaintext') is None  # Not yet decrypted
        )
    
    def process(self, envelope: Envelope, db: sqlite3.Connection) -> List[Envelope]:
        """Decrypt transit layer."""
        try:
            # Runtime validation - ensure we have TransitEnvelope fields
            transit_env = cast_envelope(envelope, TransitEnvelope)
        except TypeError as e:
            envelope['error'] = str(e)
            return []
        
        # Fetch transit key
        cursor = db.execute(
            "SELECT network_id, secret FROM transit_keys WHERE key_id = ?",
            (transit_env['transit_key_id'],)
        )
        key_row = cursor.fetchone()
        
        if not key_row:
            envelope['error'] = f"Transit key not found: {transit_env['transit_key_id']}"
            envelope['missing_deps'] = [transit_env['transit_key_id']]
            envelope['deps_included_and_valid'] = False
            return [envelope]
        
        try:
            # Transit ciphertext format: [24 bytes nonce][remaining ciphertext]
            if len(transit_env['transit_ciphertext']) < 25:
                envelope['error'] = "Transit ciphertext too short"
                return []
            
            nonce = transit_env['transit_ciphertext'][:24]
            ciphertext = transit_env['transit_ciphertext'][24:]
            
            # Decrypt
            plaintext = decrypt(ciphertext, key_row['secret'], nonce)
            
            # Parse decrypted data (JSON)
            transit_data = json.loads(plaintext.decode('utf-8'))
            
            # Update envelope with decrypted data
            envelope['transit_plaintext'] = plaintext
            envelope['network_id'] = key_row['network_id']
            envelope['event_key_id'] = transit_data.get('event_key_id')
            envelope['event_ciphertext'] = bytes.fromhex(transit_data.get('event_ciphertext', ''))
            
            # Event ID is hash of event ciphertext
            envelope['event_id'] = hash(envelope['event_ciphertext']).hex()
            
            return [envelope]
            
        except Exception as e:
            envelope['error'] = f"Transit decryption failed: {str(e)}"
            return []