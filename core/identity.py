"""
Core identity management.

Identity is a first-class framework feature that handles cryptographic identity
creation, storage, and operations. This avoids bootstrapping issues with identity
events and provides a clean foundation for protocols.
"""
import hashlib
import time
from typing import Optional, List, Dict, Any
import sqlite3
from core import crypto


class Identity:
    """Represents a cryptographic identity."""

    def __init__(self, identity_id: str, private_key: bytes, public_key: bytes, name: str = "User"):
        self.id = identity_id
        self.private_key = private_key
        self.public_key = public_key
        self.name = name

    def sign(self, data: bytes) -> bytes:
        """Sign data with identity private key."""
        return crypto.sign(data, self.private_key)

    def verify_signature(self, data: bytes, signature: bytes) -> bool:
        """Verify signature with public key."""
        return crypto.verify(data, signature, self.public_key)

    def to_dict(self) -> Dict[str, Any]:
        """Return identity as dictionary (without private key)."""
        return {
            'identity_id': self.id,
            'name': self.name,
            'public_key': self.public_key.hex()
        }


def create_identity(name: str = "User", db_path: str = "quiet.db") -> Identity:
    """
    Create new identity with keypair.

    Args:
        name: Display name for identity
        db_path: Path to database (defaults to quiet.db)

    Returns:
        New Identity instance
    """
    # Generate keypair
    private_key, public_key = crypto.generate_keypair()

    # Create deterministic ID from public key
    h = hashlib.blake2b(public_key, digest_size=16)
    identity_id = h.hexdigest()

    # Store in database
    from core.db import get_connection
    db = get_connection(db_path)
    try:
        db.execute("""
            INSERT INTO core_identities (
                identity_id, name, private_key, public_key, created_at
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            identity_id,
            name,
            private_key,
            public_key,
            int(time.time() * 1000)
        ))
        db.commit()
    finally:
        db.close()

    return Identity(identity_id, private_key, public_key, name)


def sign_with_identity(public_key_hex: str, data: bytes, db: Optional[Any] = None) -> str:
    """
    Sign data using the identity with the given public key.

    Args:
        public_key_hex: The public key of the identity to use for signing
        data: The data to sign
        db: Optional database connection or path

    Returns:
        The signature as a hex string

    Raises:
        ValueError: If no identity with the given public key is found
    """
    # Handle different db parameter types
    if db is None:
        db_path = "quiet.db"
        from core.db import get_connection
        db_conn = get_connection(db_path)
        should_close = True
    elif isinstance(db, str):
        from core.db import get_connection
        db_conn = get_connection(db)
        should_close = True
    else:
        db_conn = db
        should_close = False

    try:
        # Find identity by public key
        cursor = db_conn.execute("""
            SELECT identity_id, private_key, public_key
            FROM core_identities
            WHERE public_key = ?
        """, (bytes.fromhex(public_key_hex),))

        row = cursor.fetchone()
        if not row:
            raise ValueError(f"No identity found with public key {public_key_hex}")

        # Create identity object
        identity = Identity(
            identity_id=row[0],
            private_key=row[1],  # Already bytes from database
            public_key=row[2]     # Already bytes from database
        )

        # Sign the data
        return identity.sign(data).hex()

    finally:
        if should_close and db_conn:
            db_conn.close()


def get_identity(identity_id: str, db: Optional[Any] = None) -> Optional[Identity]:
    """
    Retrieve identity from database.

    Args:
        identity_id: Identity to retrieve
        db: Database connection or path (defaults to "quiet.db")

    Returns:
        Identity instance or None if not found
    """
    # Handle different db parameter types
    if db is None:
        db_path = "quiet.db"
        from core.db import get_connection
        db_conn = get_connection(db_path)
        should_close = True
    elif isinstance(db, str):
        # It's a path
        from core.db import get_connection
        db_conn = get_connection(db)
        should_close = True
    else:
        # It's a connection
        db_conn = db
        should_close = False

    try:
        cursor = db_conn.execute("""
            SELECT identity_id, name, private_key, public_key
            FROM core_identities
            WHERE identity_id = ?
        """, (identity_id,))

        row = cursor.fetchone()
        if not row:
            return None

        return Identity(
            identity_id=row['identity_id'],
            private_key=row['private_key'],
            public_key=row['public_key'],
            name=row['name']
        )
    finally:
        if should_close:
            db_conn.close()


def list_identities(db_path: str = "quiet.db") -> List[Dict[str, Any]]:
    """
    List all identities (without private keys).

    Args:
        db_path: Path to database (defaults to quiet.db)

    Returns:
        List of identity dictionaries
    """
    from core.db import get_connection
    db = get_connection(db_path)
    try:
        cursor = db.execute("""
            SELECT identity_id, name, public_key, created_at
            FROM core_identities
            ORDER BY created_at DESC
        """)

        identities = []
        for row in cursor:
            identities.append({
                'identity_id': row['identity_id'],
                'name': row['name'],
                'public_key': row['public_key'].hex() if isinstance(row['public_key'], bytes) else row['public_key'],
                'created_at': row['created_at']
            })

        return identities
    finally:
        db.close()


def delete_identity(identity_id: str, db_path: str = "quiet.db") -> bool:
    """
    Delete an identity.

    Args:
        identity_id: Identity to delete
        db_path: Path to database (defaults to quiet.db)

    Returns:
        True if deleted, False if not found
    """
    from core.db import get_connection
    db = get_connection(db_path)
    try:
        cursor = db.execute("""
            DELETE FROM core_identities WHERE identity_id = ?
        """, (identity_id,))

        db.commit()
        return cursor.rowcount > 0
    finally:
        db.close()


def export_identity(identity_id: str, db_path: str = "quiet.db") -> Optional[Dict[str, Any]]:
    """
    Export identity for backup (includes private key).

    Args:
        identity_id: Identity to export
        db_path: Path to database (defaults to quiet.db)

    Returns:
        Identity data including private key, or None if not found
    """
    identity = get_identity(identity_id, db_path)
    if not identity:
        return None

    return {
        'identity_id': identity.id,
        'name': identity.name,
        'private_key': identity.private_key.hex(),
        'public_key': identity.public_key.hex(),
        'exported_at': int(time.time() * 1000)
    }


def import_identity(data: Dict[str, Any], db_path: str = "quiet.db") -> Identity:
    """
    Import identity from backup.

    Args:
        data: Exported identity data
        db_path: Path to database (defaults to quiet.db)

    Returns:
        Imported Identity instance
    """
    identity_id = data['identity_id']
    name = data.get('name', 'Imported User')
    private_key = bytes.fromhex(data['private_key'])
    public_key = bytes.fromhex(data['public_key'])

    # Store in database
    from core.db import get_connection
    db = get_connection(db_path)
    try:
        db.execute("""
            INSERT OR REPLACE INTO core_identities (
                identity_id, name, private_key, public_key, created_at
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            identity_id,
            name,
            private_key,
            public_key,
            int(time.time() * 1000)
        ))
        db.commit()
    finally:
        db.close()

    return Identity(identity_id, private_key, public_key, name)


# Core API functions for use by API.py - they receive db_path from API
def core_identity_create(params: Dict[str, Any], db_path: str) -> Dict[str, Any]:
    """Create a new core identity."""
    name = params.get('name', 'User')
    identity = create_identity(name, db_path)
    return {
        "ids": {"identity": identity.id},
        "data": identity.to_dict()
    }


def core_identity_get(params: Dict[str, Any], db_path: str) -> Dict[str, Any]:
    """Get a core identity by ID."""
    identity_id = params.get('identity_id')
    if not identity_id:
        return {"error": "identity_id required"}

    identity = get_identity(identity_id, db_path)  # db_path gets handled by get_identity
    if not identity:
        return {"error": f"Identity {identity_id} not found"}

    return {"data": identity.to_dict()}


def core_identity_list(params: Dict[str, Any], db_path: str) -> Dict[str, Any]:
    """List all core identities."""
    identities = list_identities(db_path)
    return {"data": {"identities": identities}}


def core_identity_delete(params: Dict[str, Any], db_path: str) -> Dict[str, Any]:
    """Delete a core identity."""
    identity_id = params.get('identity_id')
    if not identity_id:
        return {"error": "identity_id required"}

    deleted = delete_identity(identity_id, db_path)
    if not deleted:
        return {"error": f"Identity {identity_id} not found"}

    return {"data": {"deleted": True, "identity_id": identity_id}}


def core_identity_export(params: Dict[str, Any], db_path: str) -> Dict[str, Any]:
    """Export a core identity for backup."""
    identity_id = params.get('identity_id')
    if not identity_id:
        return {"error": "identity_id required"}

    exported = export_identity(identity_id, db_path)
    if not exported:
        return {"error": f"Identity {identity_id} not found"}

    return {"data": exported}


def core_identity_import(params: Dict[str, Any], db_path: str) -> Dict[str, Any]:
    """Import a core identity from backup."""
    if 'identity_id' not in params or 'private_key' not in params or 'public_key' not in params:
        return {"error": "Missing required fields: identity_id, private_key, public_key"}

    identity = import_identity(params, db_path)
    return {
        "ids": {"identity": identity.id},
        "data": identity.to_dict()
    }
