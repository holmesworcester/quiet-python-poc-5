"""
Read-only database wrapper to ensure queries can't modify data.
"""
import sqlite3
from typing import Any, Optional


class ReadOnlyConnection:
    """
    A read-only wrapper around sqlite3.Connection that prevents modifications.
    """
    
    def __init__(self, connection: sqlite3.Connection):
        self._conn = connection
        self._conn.row_factory = sqlite3.Row
        
    def execute(self, sql: str, parameters: tuple = ()) -> sqlite3.Cursor:
        """Execute a SQL query (read-only)."""
        # Check if this is a modifying query
        sql_upper = sql.upper().strip()
        modifying_keywords = ['INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'ALTER', 'REPLACE']
        
        for keyword in modifying_keywords:
            if sql_upper.startswith(keyword):
                raise PermissionError(f"Read-only connection cannot execute {keyword} statements")
        
        return self._conn.execute(sql, parameters)
    
    def executemany(self, sql: str, seq_of_parameters) -> sqlite3.Cursor:
        """Execute many SQL queries (read-only)."""
        raise PermissionError("Read-only connection cannot execute multiple statements")
    
    def executescript(self, sql_script: str) -> sqlite3.Cursor:
        """Execute a SQL script (read-only)."""
        raise PermissionError("Read-only connection cannot execute scripts")
    
    def commit(self):
        """Commit is a no-op for read-only connections."""
        pass
    
    def rollback(self):
        """Rollback is a no-op for read-only connections."""
        pass
    
    def close(self):
        """Close the underlying connection."""
        # Don't actually close - let the owner of the real connection handle that
        pass
    
    def cursor(self) -> sqlite3.Cursor:
        """Get a cursor from the underlying connection."""
        return self._conn.cursor()
    
    @property
    def row_factory(self):
        """Get row factory."""
        return self._conn.row_factory
    
    @row_factory.setter
    def row_factory(self, factory):
        """Set row factory."""
        self._conn.row_factory = factory


def get_readonly_connection(connection: sqlite3.Connection) -> ReadOnlyConnection:
    """
    Get a read-only wrapper around a database connection.
    
    Args:
        connection: The underlying SQLite connection
        
    Returns:
        A read-only wrapper that prevents modifications
    """
    return ReadOnlyConnection(connection)