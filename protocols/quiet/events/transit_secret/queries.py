"""
Queries for transit secret event type.
"""
from core.db import ReadOnlyConnection
from typing import Dict, Any, List
import sqlite3
from core.queries import query
from protocols.quiet.client import TransitKeyListParams, TransitKeyRecord


@query(param_type=TransitKeyListParams, result_type=list[TransitKeyRecord])
def list(db: ReadOnlyConnection, params: Dict[str, Any]) -> List[Dict[str, Any]]:
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
