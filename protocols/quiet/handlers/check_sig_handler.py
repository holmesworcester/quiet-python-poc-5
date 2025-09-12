"""
Handler that checks signatures on events.
"""
import json
from typing import List, Dict, Any
import sqlite3
from core.handler import Handler
from core.crypto import verify, sign, hash
from core.types import Envelope, DecryptedEnvelope, validate_envelope_fields, cast_envelope


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
        """Process envelopes that need signature checking or identity events to store keys."""
        # Process identity events to extract signing keys
        if (envelope.get('event_type') == 'identity' and 
            envelope.get('self_created') and 
            envelope.get('local_metadata', {}).get('private_key')):
            return True
            
        # Process other events that need signature checking
        return (
            validate_envelope_fields(envelope, {'event_plaintext'}) and
            envelope.get('sig_checked') is not True
        )
    
    def process(self, envelope: Envelope, db: sqlite3.Connection) -> List[Envelope]:
        """Check event signature, sign self-created events, or store identity keys."""
        
        # Handle identity events - store signing key
        if (envelope.get('event_type') == 'identity' and 
            envelope.get('self_created') and 
            envelope.get('local_metadata', {}).get('private_key')):
            return self._store_identity_key(envelope, db)
        
        # Runtime validation
        if not envelope.get('event_plaintext'):
            envelope['error'] = "Missing event_plaintext"
            return []
        
        event_data = envelope['event_plaintext']
        
        # Handle self-created events by signing them
        if envelope.get('self_created') and not event_data.get('signature'):
            return self._sign_self_created(envelope, db)
        
        # Get peer_id (public key) from event
        # For network and group events, the creator_id is the peer_id
        peer_id = event_data.get('peer_id')
        if not peer_id and event_data.get('type') in ['network', 'group']:
            peer_id = event_data.get('creator_id')
        
        if not peer_id:
            envelope['error'] = "No peer_id in event"
            envelope['sig_checked'] = False  # Mark as checked but failed
            return [envelope]
        
        # Get signature
        signature_hex = event_data.get('signature')
        if not signature_hex:
            envelope['error'] = "No signature in event"
            envelope['sig_checked'] = False  # Mark as checked but failed
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
                envelope['sig_checked'] = True
                envelope['peer_id'] = peer_id
            else:
                envelope['error'] = "Invalid signature"
                
        except Exception as e:
            envelope['error'] = f"Signature check failed: {str(e)}"
        
        return [envelope]
    
    def _sign_self_created(self, envelope: Envelope, db: sqlite3.Connection) -> List[Envelope]:
        """Sign a self-created event using stored private key."""
        event_data = envelope['event_plaintext']
        peer_id = envelope.get('peer_id') or event_data.get('peer_id')
        
        if not peer_id:
            envelope['error'] = "No peer_id for self-created event"
            envelope['sig_checked'] = False
            return [envelope]
        
        # Get private key from signing_keys table
        cursor = db.execute("""
            SELECT private_key FROM signing_keys 
            WHERE peer_id = ? 
            LIMIT 1
        """, (peer_id,))
        row = cursor.fetchone()
        
        if not row or not row['private_key']:
            envelope['error'] = "No private key found for self-created event"
            envelope['sig_checked'] = False
            return [envelope]
        
        private_key_hex = row['private_key']
        
        try:
            # Create a copy without signature for signing
            event_copy = dict(event_data)
            event_copy.pop('signature', None)
            
            # Canonical JSON
            message = json.dumps(event_copy, sort_keys=True).encode()
            
            # Sign
            private_key = bytes.fromhex(private_key_hex)
            signature = sign(message, private_key)
            
            # Add signature to event
            event_data['signature'] = signature.hex()
            
            # Mark as self-signed and sig_checked
            envelope['self_signed'] = True
            envelope['sig_checked'] = True
            
        except Exception as e:
            envelope['error'] = f"Failed to sign self-created event: {str(e)}"
            envelope['sig_checked'] = False
        
        return [envelope]
    
    def _store_identity_key(self, envelope: Envelope, db: sqlite3.Connection) -> List[Envelope]:
        """Store private key from identity event for future signing."""
        event_data = envelope['event_plaintext']
        peer_id = event_data.get('peer_id')
        network_id = event_data.get('network_id')
        private_key = envelope['local_metadata']['private_key']
        
        if not peer_id or not network_id:
            # Pass through - not our concern
            return [envelope]
        
        try:
            # Store the signing key
            db.execute("""
                INSERT OR REPLACE INTO signing_keys (peer_id, network_id, private_key, created_at)
                VALUES (?, ?, ?, ?)
            """, (peer_id, network_id, private_key, event_data.get('created_at', 0)))
            db.commit()
            
            # Now sign the identity event itself
            return self._sign_self_created(envelope, db)
            
        except Exception as e:
            # Log error but pass envelope through
            print(f"Failed to store identity key: {e}")
            return [envelope]