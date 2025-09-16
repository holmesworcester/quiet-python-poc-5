"""Debug test to check if user events are created."""

import sqlite3
import uuid
from core.pipeline import PipelineRunner


def test_user_creation() -> None:
    """Test that create_network creates user events with existing identity."""

    db = sqlite3.connect(':memory:')
    pipeline = PipelineRunner(verbose=True)

    alice_id = str(uuid.uuid4())
    network_id = str(uuid.uuid4())

    # Create Alice's identity first
    print("\n=== Creating Alice identity ===")
    result = pipeline.run(
        protocol_dir='protocols/quiet',
        db=db,
        commands=[{
            'name': 'create_identity',
            'params': {
                'name': 'Alice',
                'identity_id': alice_id
            }
        }]
    )

    # Create network with Alice's existing identity
    print("\n=== Creating network ===")
    result = pipeline.run(
        protocol_dir='protocols/quiet',
        db=db,
        commands=[{
            'name': 'create_network',
            'params': {
                'name': 'Test Network',
                'network_id': network_id,
                'identity_id': alice_id,
                'username': 'Alice'  # Pass username for user event
            }
        }]
    )

    # Check if user was created
    cursor = db.cursor()
    users = cursor.execute("SELECT * FROM users").fetchall()
    print(f"\n=== Users in database: {len(users)} ===")
    for user in users:
        print(f"User: {user}")

    # Check identities
    identities = cursor.execute("SELECT identity_id, name FROM identities").fetchall()
    print(f"\n=== Identities: {len(identities)} ===")
    for identity in identities:
        print(f"Identity: {identity}")


if __name__ == '__main__':
    test_user_creation()
