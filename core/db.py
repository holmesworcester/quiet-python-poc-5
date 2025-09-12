"""
Database setup and utilities with read-only support.
"""
import sqlite3
from typing import Any, Optional
import os


def _load_schema_file(schema_file: str, conn: sqlite3.Connection):
    """Load a schema file into the database."""
    with open(schema_file, 'r') as f:
        schema_sql = f.read()
        for statement in schema_sql.split(';'):
            statement = statement.strip()
            if statement:
                conn.execute(statement + ';')


def get_connection(db_path: str = "quiet.db") -> sqlite3.Connection:
    """Get a database connection with proper settings."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_database(conn: sqlite3.Connection, protocol_dir: str = None):
    """Initialize database schema.
    
    The framework doesn't define any tables itself - all schema comes from:
    1. Handler-specific .schema.sql files in handlers/
    2. Event type-specific .schema.sql files in events/
    3. Any top-level .schema.sql files in the protocol directory
    """
    
    if protocol_dir:
        import glob
        import os
        
        # Load any top-level schema files in the protocol directory
        for schema_file in glob.glob(os.path.join(protocol_dir, '*.schema.sql')):
            _load_schema_file(schema_file, conn)
        
        # Load event type schemas
        events_dir = os.path.join(protocol_dir, 'events')
        if os.path.exists(events_dir):
            # Look in subdirectories for event type schemas
            for event_type_dir in os.listdir(events_dir):
                event_type_path = os.path.join(events_dir, event_type_dir)
                if os.path.isdir(event_type_path):
                    for schema_file in glob.glob(os.path.join(event_type_path, '*.schema.sql')):
                        _load_schema_file(schema_file, conn)
            
            # Also check for schemas directly in events/
            for schema_file in glob.glob(os.path.join(events_dir, '*.schema.sql')):
                _load_schema_file(schema_file, conn)
        
        # Load handler schemas
        handlers_dir = os.path.join(protocol_dir, 'handlers')
        if os.path.exists(handlers_dir):
            # Look in subdirectories for handler schemas
            for handler_dir in os.listdir(handlers_dir):
                handler_path = os.path.join(handlers_dir, handler_dir)
                if os.path.isdir(handler_path):
                    for schema_file in glob.glob(os.path.join(handler_path, '*.schema.sql')):
                        _load_schema_file(schema_file, conn)
            
            # Also check for schemas directly in handlers/
            for schema_file in glob.glob(os.path.join(handlers_dir, '*.schema.sql')):
                _load_schema_file(schema_file, conn)
    
    conn.commit()


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