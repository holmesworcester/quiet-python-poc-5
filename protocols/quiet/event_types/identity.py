"""
Identity event type - creates a peer identity with no dependencies.
"""
import json
import time
from typing import Dict, Any, Optional
import sqlite3
from core.crypto import generate_keypair, sign, verify, hash


class IdentityEventType:
    """
    Identity event - establishes a peer's public key.
    No dependencies required.
    """
    
    @staticmethod
    def validate(event_data: Dict[str, Any], envelope_metadata: Dict[str, Any]) -> bool:
        """
        Validate an identity event.
        - Must have peer_id (public key)
        - Must have valid self-signature
        - No dependencies required
        """
        if 'type' not in event_data or event_data['type'] != 'identity':
            return False
            
        if 'peer_id' not in event_data:
            return False
            
        if 'signature' not in event_data:
            return False
            
        # Verify self-signature
        # Remove signature field for verification
        event_copy = dict(event_data)
        signature = bytes.fromhex(event_copy.pop('signature'))
        peer_id = bytes.fromhex(event_data['peer_id'])
        
        # Canonical JSON
        message = json.dumps(event_copy, sort_keys=True).encode()
        
        return verify(message, signature, peer_id)
    
    @staticmethod
    def create(params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new identity event.
        Params:
        - network_id: The network this identity is for
        """
        private_key, public_key = generate_keypair()
        
        event = {
            'type': 'identity',
            'peer_id': public_key.hex(),
            'network_id': params['network_id'],
            'created_at': int(time.time() * 1000)
        }
        
        # Sign the event
        message = json.dumps(event, sort_keys=True).encode()
        signature = sign(message, private_key)
        event['signature'] = signature.hex()
        
        # Return event and private key (to be stored locally)
        return {
            'event': event,
            'private_key': private_key.hex()
        }
    
    @staticmethod
    def project(event_data: Dict[str, Any], db: sqlite3.Connection) -> Dict[str, Any]:
        """
        Project identity event to state.
        Adds peer to peers table.
        """
        peer_id = event_data['peer_id']
        network_id = event_data['network_id']
        
        # Add to peers table
        db.execute("""
            INSERT OR IGNORE INTO peers (peer_id, network_id, public_key, added_at)
            VALUES (?, ?, ?, ?)
        """, (
            peer_id,
            network_id,
            bytes.fromhex(peer_id),
            int(time.time() * 1000)
        ))
        
        return {
            'op': 'add_peer',
            'peer_id': peer_id,
            'network_id': network_id
        }