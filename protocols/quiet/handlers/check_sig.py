"""
Handler that checks signatures on events.
"""
import json
from typing import List
import sqlite3
from core.envelope import Envelope
from core.handler import Handler
from core.crypto import verify


class CheckSigHandler(Handler):
    """
    Checks signatures on events.
    Consumes: envelopes with event_plaintext where sig_checked is not True
    Emits: envelopes with sig_checked=True or error
    """
    
    @property
    def name(self) -> str:
        return "check_sig"
    
    def filter(self, envelope: Envelope) -> bool:
        """Process envelopes that need signature checking."""
        return (
            envelope.event_plaintext is not None and
            envelope.sig_checked is not True
        )
    
    def process(self, envelope: Envelope, db: sqlite3.Connection) -> List[Envelope]:
        """Check event signature."""
        
        event_data = envelope.event_plaintext
        
        # Get peer_id (public key) from event
        peer_id = event_data.get('peer_id')
        if not peer_id:
            envelope.error = "No peer_id in event"
            return [envelope]
        
        # Get signature
        signature_hex = event_data.get('signature')
        if not signature_hex:
            envelope.error = "No signature in event"
            return [envelope]
        
        try:
            # Remove signature for verification
            event_copy = dict(event_data)
            event_copy.pop('signature')
            
            # Canonical JSON
            message = json.dumps(event_copy, sort_keys=True).encode()
            
            # Verify
            signature = bytes.fromhex(signature_hex)
            public_key = bytes.fromhex(peer_id)
            
            if verify(message, signature, public_key):
                envelope.sig_checked = True
                envelope.peer_id = peer_id
            else:
                envelope.error = "Invalid signature"
                
        except Exception as e:
            envelope.error = f"Signature check failed: {str(e)}"
        
        return [envelope]