"""
Network queries.
"""
from typing import Dict, Any, List
from core.queries import query
from protocols.quiet.client import NetworkGetParams, NetworkRecord
from core.db import ReadOnlyConnection


@query(param_type=NetworkGetParams, result_type=list[NetworkRecord])
def get(db: ReadOnlyConnection, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Get networks with optional filtering."""
    query = "SELECT * FROM networks WHERE 1=1"
    query_params: List[Any] = []

    # Filter by network_id if provided
    if 'network_id' in params and params['network_id']:
        query += " AND network_id = ?"
        query_params.append(params['network_id'])

    # Filter by peer_id if provided
    # networks table does not store peer_id; if supplied, ignore (scope with other queries instead)

    cursor = db.execute(query, tuple(query_params))
    columns = [desc[0] for desc in cursor.description]
    results = []
    
    for row in cursor.fetchall():
        network = dict(zip(columns, row))
        results.append(network)
    
    return results
