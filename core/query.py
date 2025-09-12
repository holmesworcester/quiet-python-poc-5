"""
Base class and decorators for query functions with read-only database access.
"""
from typing import Any, Callable, TypeVar, Protocol
import sqlite3
from .readonly_db import ReadOnlyConnection, get_readonly_connection

T = TypeVar('T')


class QueryFunc(Protocol):
    """Protocol for query functions that read from the database."""
    def __call__(self, db: ReadOnlyConnection, **kwargs: Any) -> Any:
        ...


def query(func: Callable) -> Callable:
    """
    Decorator for query functions that enforces read-only database access.
    
    Query functions receive a ReadOnlyConnection that prevents modifications.
    """
    import functools
    import inspect
    
    # Check signature
    sig = inspect.signature(func)
    params = list(sig.parameters.keys())
    
    if not params or params[0] != 'db':
        raise TypeError(
            f"{func.__name__} must have 'db' as first parameter for read-only connection"
        )
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # If first argument is a regular connection, wrap it
        if args and isinstance(args[0], sqlite3.Connection):
            readonly_conn = get_readonly_connection(args[0])
            args = (readonly_conn,) + args[1:]
        elif args and not isinstance(args[0], ReadOnlyConnection):
            raise TypeError(
                f"{func.__name__} must receive a database connection as first argument"
            )
        
        return func(*args, **kwargs)
    
    # Mark as query function
    wrapper._is_query = True
    return wrapper


class QueryRegistry:
    """Registry for query functions in a module."""
    
    def __init__(self):
        self._queries: dict[str, Callable] = {}
    
    def register(self, name: str, query_func: Callable):
        """Register a query function."""
        if not getattr(query_func, '_is_query', False):
            raise ValueError(f"{name} must be decorated with @query")
        self._queries[name] = query_func
    
    def get(self, name: str) -> Callable:
        """Get a query function by name."""
        return self._queries.get(name)
    
    def list_queries(self) -> list[str]:
        """List all registered query names."""
        return sorted(self._queries.keys())