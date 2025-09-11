"""
Handler that decrypts event-layer encryption.
"""
import json
from typing import List
import sqlite3
from core.envelope import Envelope  
from core.handler import Handler
from core.crypto import decrypt


class DecryptEventHandler(Handler):
    """
    Decrypts event-layer encryption or extracts plaintext for unencrypted events.
    Consumes: envelopes with event_ciphertext and optionally event_key_id
    Emits: envelopes with event_plaintext and event_type
    """
    
    @property
    def name(self) -> str:
        return "decrypt_event"
    
    def filter(self, envelope: Envelope) -> bool:
        """Process envelopes ready for event decryption."""
        return (
            envelope.event_ciphertext is not None and
            envelope.event_plaintext is None
        )
    
    def process(self, envelope: Envelope, db: sqlite3.Connection) -> List[Envelope]:
        """Decrypt event layer or extract plaintext."""
        
        # Check if this needs actual decryption
        if envelope.event_key_id:
            # This event is encrypted, need to decrypt
            # For now, we'll skip this case
            envelope.error = "Event-layer decryption not yet implemented"
            return [envelope]
        else:
            # No encryption, just parse the JSON
            try:
                event_data = json.loads(envelope.event_ciphertext.decode('utf-8'))
                envelope.event_plaintext = event_data
                envelope.event_type = event_data.get('type')
                return [envelope]
            except Exception as e:
                envelope.error = f"Failed to parse event: {str(e)}"
                return [envelope]