"""
Integration tests for the full handler pipeline.
"""
import pytest
import time
from protocols.quiet.handlers.receive_from_network import ReceiveFromNetworkHandler
from protocols.quiet.handlers.resolve_deps import ResolveDepsHandler
from protocols.quiet.handlers.transit_crypto import handler as transit_crypto_handler
from protocols.quiet.handlers.remove import handler as remove_handler
from protocols.quiet.handlers.event_crypto import handler as event_crypto_handler
from protocols.quiet.handlers.event_store import handler as event_store_handler
from protocols.quiet.handlers.signature import handler as signature_handler
from protocols.quiet.handlers.validate import ValidateHandler
from protocols.quiet.handlers.resolve_deps import handler as unblock_deps_handler
from .test_base import HandlerTestBase


class TestPipelineIntegration(HandlerTestBase):
    """Test full pipeline integration with identity creation."""
    
    def setup_method(self):
        """Set up handlers and test data."""
        super().setup_method()
        
        # Initialize handlers that need instances
        self.receive_handler = ReceiveFromNetworkHandler()
        self.resolve_deps_handler = ResolveDepsHandler()
        self.validate_handler = ValidateHandler()
        
        # Add test validator for identity events
        class IdentityValidator:
            @staticmethod
            def validate(envelope):
                plaintext = envelope.get('event_plaintext', {})
                return (
                    plaintext.get('type') == 'identity' and
                    'peer_id' in plaintext and
                    'public_key' in plaintext
                )
        
        self.validate_handler.validators['identity'] = IdentityValidator
    
    def test_identity_creation_pipeline(self):
        """Test creating an identity through the full creation pipeline."""
        # Start with a command result (identity plaintext)
        envelope = self.create_envelope(
            self_created=True,
            event_plaintext={
                "type": "identity",
                "peer_id": "alice_peer_id",
                "public_key": "alice_public_key",
                "created_at": int(time.time() * 1000)
            },
            peer_id="alice_peer_id",
            deps=["identity:alice_peer_id"]  # Self-referential for signing
        )
        
        # 1. Resolve deps (need our own identity to sign)
        # First store our identity with private key
        self.db.execute("""
            INSERT INTO signing_keys (peer_id, private_key)
            VALUES (?, ?)
        """, ("alice_peer_id", "alice_private_key"))
        self.db.commit()
        
        results = self.resolve_deps_handler.process(envelope, self.db)
        assert len(results) == 1
        envelope = results[0]
        assert envelope['deps_included_and_valid'] is True
        
        # 2. Sign the event
        envelope = signature_handler(envelope)
        assert 'signature' in envelope['event_plaintext']
        assert 'event_id' in envelope  # Generated from canonical signed plaintext
        assert envelope['sig_checked'] is True
        
        # 3. Validate (would normally check group membership first)
        results = self.validate_handler.process(envelope, self.db)
        assert len(results) == 1
        envelope = results[0]
        assert envelope['validated'] is True
        
        # 4. Encrypt for storage
        envelope = event_crypto_handler(envelope)
        assert 'event_ciphertext' in envelope
        assert 'key_ref' in envelope
        assert envelope['write_to_store'] is True
        
        # 5. Store the event
        envelope = event_store_handler(envelope, self.db)
        assert envelope['stored'] is True
        
        # Verify it's in the database
        cursor = self.db.execute(
            "SELECT * FROM events WHERE event_id = ?",
            (envelope['event_id'],)
        )
        row = cursor.fetchone()
        assert row is not None
        assert row['event_type'] == 'identity'
    
    def test_incoming_identity_pipeline(self):
        """Test receiving an identity through the incoming pipeline."""
        # Simulate raw network data with transit encryption
        transit_key_id = b"network_transit_key_123"
        event_data = b"encrypted_event_data"
        raw_data = transit_key_id + event_data
        
        # 0. Prepare transit key
        self.db.execute("""
            INSERT INTO transit_keys (transit_key_id, transit_secret, network_id)
            VALUES (?, ?, ?)
        """, (transit_key_id.hex(), b"network_transit_secret", "test_network"))
        self.db.commit()
        
        # 1. Receive from network
        envelope = self.create_envelope(
            origin_ip="192.168.1.100",
            origin_port=8080,
            received_at=int(time.time() * 1000),
            raw_data=raw_data
        )
        
        results = self.receive_handler.process(envelope, self.db)
        assert len(results) == 1
        envelope = results[0]
        assert envelope['transit_key_id'] == transit_key_id.hex()
        assert envelope['deps'] == [f"transit_key:{transit_key_id.hex()}"]
        
        # 2. Resolve transit key dependency
        results = self.resolve_deps_handler.process(envelope, self.db)
        assert len(results) == 1
        envelope = results[0]
        assert envelope['deps_included_and_valid'] is True
        
        # 3. Decrypt transit layer
        # Add stub data for decryption
        envelope['key_ref'] = {"kind": "peer", "id": "bob_peer_id"}
        envelope = transit_crypto_handler(envelope)
        assert 'event_ciphertext' in envelope
        assert 'key_ref' in envelope
        
        # 4. Early remove check (by event_id)
        envelope['event_id'] = "bob_identity_event"
        result = remove_handler(envelope, self.db)
        assert result is not None  # Not removed
        assert result['should_remove'] is False
        envelope = result
        
        # 5. Resolve deps for decryption (need bob's identity)
        envelope['deps'] = ["identity:bob_peer_id"]
        # Store Bob's identity
        self.db.execute("""
            INSERT INTO events (event_id, event_type, stored_at, validated)
            VALUES (?, ?, ?, ?)
        """, ("bob_peer_id", "identity", 1000, 1))
        self.db.commit()
        
        results = self.resolve_deps_handler.process(envelope, self.db)
        assert len(results) == 1
        envelope = results[0]
        
        # 6. Decrypt event (stub unsealing for peer)
        envelope = event_crypto_handler(envelope)
        assert envelope['event_type'] == 'key'  # Unsealed as key event
        assert envelope['sig_checked'] is True  # Key events bypass sig check
        
        # 7. Store the event
        envelope = event_store_handler(envelope, self.db)
        assert envelope['stored'] is True
    
    def test_blocked_event_unblocking(self):
        """Test that blocked events get unblocked when dependencies arrive."""
        # Create a message that depends on a missing identity
        blocked_envelope = self.create_envelope(
            event_id="blocked_message",
            event_type="message",
            event_plaintext={
                "type": "message",
                "content": "Hello",
                "peer_id": "charlie_peer_id"
            },
            deps=["identity:charlie_peer_id"],
            sig_checked=False
        )
        
        # Try to resolve deps - will fail
        results = self.resolve_deps_handler.process(blocked_envelope, self.db)
        assert len(results) == 0  # Dropped due to missing deps
        
        # Process through unblock_deps to record blocking
        unblock_envelope = self.create_envelope(
            missing_deps=True,
            event_id="blocked_message",
            missing_deps_list=["identity:charlie_peer_id"]
        )
        results = unblock_deps_handler(unblock_envelope, self.db)
        assert len(results) == 1  # Just returns the envelope
        
        # Now Charlie's identity arrives and gets validated
        charlie_envelope = self.create_envelope(
            validated=True,
            event_id="charlie_peer_id",
            event_type="identity"
        )
        
        # Store Charlie's identity
        self.db.execute("""
            INSERT INTO events (event_id, event_type, stored_at, validated, purged)
            VALUES (?, ?, ?, ?, ?)
        """, ("charlie_peer_id", "identity", int(time.time() * 1000), 1, 0))
        self.db.commit()
        
        # Process Charlie through unblock_deps
        results = unblock_deps_handler(charlie_envelope, self.db)
        
        # Should unblock the message
        assert len(results) == 2
        assert results[0] == charlie_envelope
        
        unblocked = results[1]
        assert unblocked['event_id'] == 'blocked_message'
        assert unblocked['unblocked'] is True
        assert unblocked['retry_count'] == 1
    
    def test_invalid_event_purging(self):
        """Test that invalid events get purged from storage."""
        # Create an invalid identity (missing required fields)
        invalid_envelope = self.create_envelope(
            event_id="invalid_identity",
            event_plaintext={
                "type": "identity"
                # Missing peer_id and public_key
            },
            sig_checked=True,
            write_to_store=True
        )
        
        # Store it first
        invalid_envelope = event_store_handler(invalid_envelope, self.db)
        assert invalid_envelope['stored'] is True
        
        # Try to validate - should fail and purge
        results = self.validate_handler.process(invalid_envelope, self.db)
        assert len(results) == 0  # Dropped
        
        # Check it was purged
        cursor = self.db.execute(
            "SELECT purged, purged_reason FROM events WHERE event_id = ?",
            ("invalid_identity",)
        )
        row = cursor.fetchone()
        assert row is not None
        assert row['purged'] == 1
        assert row['purged_reason'] == 'validation_failed'