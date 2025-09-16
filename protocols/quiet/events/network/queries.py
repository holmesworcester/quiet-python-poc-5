"""
Network queries.
"""
from typing import Dict, Any, List
from core.queries import query
from core.db import ReadOnlyConnection


@query
def get(db: ReadOnlyConnection, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Get networks with optional filtering."""
    query = "SELECT * FROM networks WHERE 1=1"
    query_params = []

    # Filter by network_id if provided
    if 'network_id' in params:
        query += " AND id = ?"
        query_params.append(params['network_id'])

    # Filter by peer_id if provided
    if 'peer_id' in params:
        query += " AND peer_id = ?"
        query_params.append(params['peer_id'])

    cursor = db.execute(query, query_params)
    columns = [desc[0] for desc in cursor.description]
    results = []
    
    for row in cursor.fetchall():
        network = dict(zip(columns, row))
        results.append(network)
    
    return results
