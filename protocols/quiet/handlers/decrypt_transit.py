"""
Handler that decrypts transit layer encryption.
"""
import json
from typing import List
import sqlite3
from core.envelope import Envelope
from core.handler import Handler
from core.crypto import decrypt, hash


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
            envelope.transit_key_id is not None and
            envelope.transit_ciphertext is not None and
            envelope.transit_plaintext is None  # Not yet decrypted
        )
    
    def process(self, envelope: Envelope, db: sqlite3.Connection) -> List[Envelope]:
        """Decrypt transit layer."""
        
        # Fetch transit key
        cursor = db.execute(
            "SELECT network_id, secret FROM transit_keys WHERE key_id = ?",
            (envelope.transit_key_id,)
        )
        key_row = cursor.fetchone()
        
        if not key_row:
            envelope.error = f"Transit key not found: {envelope.transit_key_id}"
            envelope.missing_deps = [envelope.transit_key_id]
            envelope.deps_included_and_valid = False
            return [envelope]
        
        try:
            # Transit ciphertext format: [24 bytes nonce][remaining ciphertext]
            if len(envelope.transit_ciphertext) < 25:
                envelope.error = "Transit ciphertext too short"
                return []
            
            nonce = envelope.transit_ciphertext[:24]
            ciphertext = envelope.transit_ciphertext[24:]
            
            # Decrypt
            plaintext = decrypt(ciphertext, key_row['secret'], nonce)
            
            # Parse decrypted data (JSON)
            transit_data = json.loads(plaintext.decode('utf-8'))
            
            # Extract event layer info
            envelope.transit_plaintext = plaintext
            envelope.network_id = key_row['network_id']
            envelope.event_key_id = transit_data.get('event_key_id')
            envelope.event_ciphertext = bytes.fromhex(transit_data.get('event_ciphertext', ''))
            
            # Event ID is hash of event ciphertext
            envelope.event_id = hash(envelope.event_ciphertext).hex()
            
            return [envelope]
            
        except Exception as e:
            envelope.error = f"Transit decryption failed: {str(e)}"
            return []