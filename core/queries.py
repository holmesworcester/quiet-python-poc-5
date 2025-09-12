"""
Queries for the Quiet protocol.
Queries are registered with the query registry and can be executed via the API.
"""
import importlib
from typing import Dict, Any, List, Callable
import sqlite3


class QueryRegistry:
    """Registry for protocol queries."""
    
    def __init__(self):
        self._queries: Dict[str, Callable] = {}
        
    def register(self, name: str, query: Callable):
        """Register a query function."""
        self._queries[name] = query
        
    def execute(self, name: str, params: Dict[str, Any], db: sqlite3.Connection) -> Any:
        """Execute a query and return results."""
        if name not in self._queries:
            raise ValueError(f"Unknown query: {name}")
            
        query = self._queries[name]
        return query(params, db)
        
    def list_queries(self) -> List[str]:
        """Return list of registered query names."""
        return sorted(self._queries.keys())


# Global query registry
query_registry = QueryRegistry()


# Event types to load queries from
EVENT_TYPES = ['identity', 'key', 'transit_secret', 'group', 'channel', 'message']

# Queries to register from each event type
QUERIES = {
    'identity': ['list'],
    'key': ['list'],
    'transit_secret': ['list'],
    'group': ['list'],
    'channel': ['list'],
    'message': ['list']
}


def register_queries():
    """Register all queries from event types."""
    
    # Register event type queries
    for event_type, query_names in QUERIES.items():
        for query_name in query_names:
            try:
                # Import the query module
                module = importlib.import_module(
                    f'protocols.quiet.events.{event_type}.queries.{query_name}'
                )
                
                # Register based on the expected function name
                if query_name == 'list':
                    # Special handling for list queries
                    if event_type == 'identity':
                        query_registry.register('identity.list', module.list_identities)
                    elif event_type == 'key':
                        query_registry.register('key.list', module.list_keys)
                    elif event_type == 'transit_secret':
                        query_registry.register('transit_secret.list', module.list_transit_keys)
                    elif event_type == 'group':
                        query_registry.register('group.list', module.list_groups)
                    elif event_type == 'channel':
                        query_registry.register('channel.list', module.list_channels)
                    elif event_type == 'message':
                        query_registry.register('message.list', module.list_messages)
                else:
                    # Generic registration for other queries
                    func_name = f"{query_name}_{event_type}"
                    if hasattr(module, func_name):
                        query_registry.register(f"{event_type}.{query_name}", getattr(module, func_name))
                        
            except ImportError as e:
                print(f"Failed to load query {query_name} for {event_type}: {e}")
    
    # Register system queries
    query_registry.register('system.dump_database', dump_database)
    query_registry.register('system.logs', get_logs)


# System query functions (moved from queries_system.py)

def dump_database(params: Dict[str, Any], db: sqlite3.Connection) -> Dict[str, List[Dict[str, Any]]]:
    """Dump all tables in the database."""
    # Get all tables
    cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    
    result = {}
    for table in tables:
        cursor = db.execute(f"SELECT * FROM {table}")
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        table_results = []
        for row in rows:
            row_dict = dict(zip(columns, row))
            # Convert bytes to hex
            for key, value in row_dict.items():
                if isinstance(value, bytes):
                    row_dict[key] = value.hex()
            table_results.append(row_dict)
        result[table] = table_results
    return result


def get_logs(params: Dict[str, Any], db: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Get processor logs (placeholder for now)."""
    limit = params.get('limit', 100)
    # In the future, this could read from a logs table
    return []


# Register queries on module load
register_queries()