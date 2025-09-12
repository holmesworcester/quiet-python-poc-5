"""
Commands for key event type.
"""
import time
from typing import Dict, Any, List
import sqlite3
from core.crypto import generate_secret, seal, hash


def create_key(params: Dict[str, Any], db: sqlite3.Connection) -> List[Dict[str, Any]]:
    """
    Create a new encryption key for a group.
    
    Params:
    - group_id: The group this key is for
    - network_id: The network this key is for
    - identity_id: The identity creating this key
    
    Returns a list of envelopes to process.
    """
    required = ['group_id', 'network_id', 'identity_id']
    for field in required:
        if field not in params:
            raise ValueError(f"{field} is required")
    
    # Fetch our identity's private key and public key
    cursor = db.cursor()
    cursor.execute("""
        SELECT private_key, public_key FROM identities 
        WHERE identity_id = ? AND network_id = ?
    """, (params['identity_id'], params['network_id']))
    
    row = cursor.fetchone()
    if not row:
        raise ValueError(f"Identity {params['identity_id']} not found")
        
    public_key = bytes.fromhex(row['public_key'])
    peer_id = row['public_key']
    
    # Generate a random encryption key
    secret = generate_secret()
    
    # Seal the secret with our public key (so we can decrypt it later)
    sealed_secret = seal(secret, public_key)
    
    # Create key event (unsigned)
    event = {
        'type': 'key',
        'peer_id': peer_id,
        'group_id': params['group_id'],
        'sealed_secret': sealed_secret.hex(),
        'network_id': params['network_id'],
        'created_at': int(time.time() * 1000)
    }
    
    # Generate key_id as hash of the event
    import json
    event_bytes = json.dumps(event, sort_keys=True).encode()
    key_id = hash(event_bytes)
    event['key_id'] = key_id.hex()
    
    # Return the event as an envelope
    envelope = {
        'event_plaintext': event,
        'event_type': 'key',
        'self_created': True,
        'peer_id': peer_id,
        'network_id': params['network_id'],
        'deps': []  # Keys don't depend on other events
    }
    
    return [envelope]