"""
Queries for transit secret event type.
"""
from typing import Dict, Any, List
import sqlite3


def list_transit_keys(params: Dict[str, Any], db: sqlite3.Connection) -> List[Dict[str, Any]]:
    """List all transit keys, optionally filtered by network_id."""
    network_id = params.get('network_id')
    
    if network_id:
        cursor = db.execute("""
            SELECT transit_key_id, peer_id, network_id, created_at 
            FROM peer_transit_keys 
            WHERE network_id = ?
            ORDER BY created_at DESC
        """, (network_id,))
    else:
        cursor = db.execute("""
            SELECT transit_key_id, peer_id, network_id, created_at 
            FROM peer_transit_keys 
            ORDER BY created_at DESC
        """)
    
    results = []
    for row in cursor:
        results.append({
            "transit_key_id": row['transit_key_id'],
            "peer_id": row['peer_id'],
            "network_id": row['network_id'],
            "created_at": row['created_at']
        })
    
    return results