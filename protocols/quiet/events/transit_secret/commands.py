"""
Commands for transit secret event type.
"""
import time
from typing import Dict, Any, List
import sqlite3
from core.crypto import generate_secret, hash


def create_transit_secret(params: Dict[str, Any], db: sqlite3.Connection) -> List[Dict[str, Any]]:
    """
    Create a new transit encryption key.
    
    Params:
    - network_id: The network this key is for
    - identity_id: The identity creating this key
    
    Returns a list of envelopes to process.
    """
    required = ['network_id', 'identity_id']
    for field in required:
        if field not in params:
            raise ValueError(f"{field} is required")
    
    # Fetch our identity's public key
    cursor = db.cursor()
    cursor.execute("""
        SELECT public_key FROM identities 
        WHERE identity_id = ? AND network_id = ?
    """, (params['identity_id'], params['network_id']))
    
    row = cursor.fetchone()
    if not row:
        raise ValueError(f"Identity {params['identity_id']} not found")
        
    peer_id = row['public_key']
    
    # Generate a random transit key
    secret = generate_secret()
    
    # Create transit secret event (unsigned)
    event = {
        'type': 'transit_secret',
        'peer_id': peer_id,
        'network_id': params['network_id'],
        'created_at': int(time.time() * 1000)
    }
    
    # Generate transit_key_id as hash of the secret
    transit_key_id = hash(secret)
    event['transit_key_id'] = transit_key_id.hex()
    
    # Store the secret in transit_keys table (local only)
    cursor.execute("""
        INSERT INTO transit_keys (key_id, network_id, secret, created_at)
        VALUES (?, ?, ?, ?)
    """, (
        transit_key_id.hex(),
        params['network_id'],
        secret,
        event['created_at']
    ))
    db.commit()
    
    # Return the event as an envelope
    envelope = {
        'event_plaintext': event,
        'event_type': 'transit_secret',
        'self_created': True,
        'peer_id': peer_id,
        'network_id': params['network_id'],
        'deps': []  # Transit secrets don't depend on other events
    }
    
    return [envelope]