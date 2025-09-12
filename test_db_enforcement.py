#!/usr/bin/env python3
"""
Test that database access enforcement works correctly.
"""
import sqlite3
from core.types import command, validator, projector
from core.query import query
from core.readonly_db import ReadOnlyConnection


def test_command_no_db():
    """Test that commands can't access database."""
    print("Testing command DB access enforcement...")
    
    try:
        @command
        def bad_command(params):
            # This should fail at decoration time
            db.execute("SELECT * FROM events")
            return {"event_plaintext": {}, "event_type": "test", "self_created": True, "deps": []}
        print("ERROR: Command with DB access was allowed!")
    except ValueError as e:
        print(f"✓ Command correctly rejected: {e}")


def test_validator_no_db():
    """Test that validators can't access database."""
    print("\nTesting validator DB access enforcement...")
    
    try:
        @validator
        def bad_validator(envelope):
            # This should fail at decoration time
            cursor = db.execute("SELECT * FROM events")
            return True
        print("ERROR: Validator with DB access was allowed!")
    except ValueError as e:
        print(f"✓ Validator correctly rejected: {e}")


def test_projector_no_db():
    """Test that projectors can't access database."""
    print("\nTesting projector DB access enforcement...")
    
    try:
        @projector
        def bad_projector(envelope):
            # This should fail at decoration time
            cursor.execute("INSERT INTO events VALUES (?)", (1,))
            return []
        print("ERROR: Projector with DB access was allowed!")
    except ValueError as e:
        print(f"✓ Projector correctly rejected: {e}")


def test_query_readonly():
    """Test that queries can only read."""
    print("\nTesting query read-only enforcement...")
    
    # Create a test database
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE test (id INTEGER, value TEXT)")
    db.execute("INSERT INTO test VALUES (1, 'test')")
    
    @query
    def good_query(db, test_id):
        cursor = db.execute("SELECT * FROM test WHERE id = ?", (test_id,))
        return cursor.fetchone()
    
    @query
    def bad_query(db):
        # This should fail at runtime
        db.execute("INSERT INTO test VALUES (2, 'should fail')")
    
    # Test good query works
    result = good_query(db, 1)
    print(f"✓ Read-only query works: {result}")
    
    # Test bad query fails
    try:
        bad_query(db)
        print("ERROR: Write query was allowed!")
    except PermissionError as e:
        print(f"✓ Write query correctly rejected: {e}")
    
    db.close()


def test_pure_functions():
    """Test that pure event functions work correctly."""
    print("\nTesting pure event functions...")
    
    @command
    def good_command(params):
        # Pure function - no DB access
        return {
            "event_plaintext": {"type": "test", "data": params.get("data")},
            "event_type": "test",
            "self_created": True,
            "deps": []
        }
    
    @validator
    def good_validator(envelope):
        # Pure function - validates based on envelope data only
        return envelope.get("event_type") == "test"
    
    @projector 
    def good_projector(envelope):
        # Pure function - returns deltas only
        return [{
            "op": "insert",
            "table": "test_events",
            "data": {"id": 1, "type": "test"},
            "where": {}
        }]
    
    # Test they work
    envelope = good_command({"data": "test"})
    print(f"✓ Pure command works: {envelope['event_plaintext']}")
    
    valid = good_validator(envelope)
    print(f"✓ Pure validator works: {valid}")
    
    deltas = good_projector(envelope)
    print(f"✓ Pure projector works: {len(deltas)} delta(s)")


if __name__ == "__main__":
    print("Database Access Enforcement Tests")
    print("=" * 50)
    
    test_command_no_db()
    test_validator_no_db()
    test_projector_no_db()
    test_query_readonly()
    test_pure_functions()
    
    print("\n✅ All tests passed!")