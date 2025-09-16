"""
Tests for resolve_deps handler.
"""
import pytest
import sys
import json
from pathlib import Path

# Add project root to path
protocol_dir = Path(__file__).parent.parent.parent
project_root = protocol_dir.parent.parent
sys.path.insert(0, str(project_root))

from protocols.quiet.handlers.resolve_deps import filter_func, handler as resolve_handler, parse_dep_ref
from protocols.quiet.tests.handlers.test_base import HandlerTestBase


class TestResolveDepsHandler:
    """Test dependency resolution handler."""

    @pytest.fixture
    def resolve_filter(self):
        """Get filter function."""
        return filter_func
    
    @pytest.mark.unit
    @pytest.mark.handler
    def test_filter_matches_when_keys_needed(self, resolve_filter):
        """Filter matches when transit/event key deps are implied."""
        # Transit stage
        env1 = {"transit_ciphertext": b"..", "transit_key_id": "tk", "deps_included_and_valid": False}
        assert resolve_filter(env1) is True
        # Event stage
        env2 = {"event_ciphertext": b"..", "event_key_id": "ek", "deps_included_and_valid": False}
        assert resolve_filter(env2) is True
    
    @pytest.mark.unit
    @pytest.mark.handler
    def test_filter_with_deps_valid(self, resolve_filter):
        """Test filter rejects envelopes with deps already valid."""
        envelope = {
            "event_type": "test",
            "event_plaintext": {"type": "test"},
            "deps_included_and_valid": True
        }
        assert resolve_filter(envelope) == False
    
    @pytest.mark.unit
    @pytest.mark.handler
    def test_filter_validated_triggers_unblock(self, resolve_filter):
        """Validated events can trigger unblocking of others."""
        envelope = {"validated": True, "event_id": "e1"}
        assert resolve_filter(envelope) is True
    
    @pytest.mark.unit
    @pytest.mark.handler
    def test_process_no_deps_array(self, resolve_filter, initialized_db):
        """If deps=[], handler marks deps valid and emits envelope."""
        envelope = {"deps": [], "event_id": "e1"}
        
        results = resolve_handler(envelope, initialized_db)
        
        assert len(results) == 1
        result = results[0]
        
        # Should mark as deps valid with no missing deps
        assert result["deps_included_and_valid"] == True
        assert result.get("missing_deps", []) == []
    
    @pytest.mark.unit
    @pytest.mark.handler
    def test_process_transit_key_dep(self, initialized_db):
        """Transit key deps resolve from local transit_keys table."""
        # Ensure transit_keys table exists in this DB
        initialized_db.execute(
            """
            CREATE TABLE IF NOT EXISTS transit_keys (
                transit_key_id TEXT PRIMARY KEY,
                transit_secret BLOB NOT NULL,
                network_id TEXT NOT NULL
            )
            """
        )
        initialized_db.execute(
            "INSERT OR REPLACE INTO transit_keys (transit_key_id, transit_secret, network_id) VALUES (?, ?, ?)",
            ("test_transit_key", b"ts", "net-1"),
        )
        envelope = {"deps": ["transit_key:test_transit_key"], "event_id": "e2"}
        results = resolve_handler(envelope, initialized_db)
        assert len(results) == 1
        res = results[0]
        assert res["deps_included_and_valid"] is True
        assert "transit_key:test_transit_key" in res["resolved_deps"]
    
    @pytest.mark.unit
    @pytest.mark.handler
    def test_process_missing_deps_blocks(self, initialized_db):
        """Missing deps cause blocking and no emission."""
        envelope = {"deps": ["identity:missing", "key:missing"], "event_id": "xx"}
        results = resolve_handler(envelope, initialized_db)
        assert results == []
    
    @pytest.mark.unit
    @pytest.mark.handler
    def test_process_preserves_envelope(self, initialized_db):
        """Test that handler preserves original envelope data."""
        envelope = {"deps": [], "event_id": "e3", "custom_field": "preserved"}
        
        results = resolve_handler(envelope, initialized_db)
        result = results[0]
        
        # Original fields should be preserved
        assert result["event_id"] == "e3"
        assert result["custom_field"] == "preserved"


class TestResolveDepsHandlerMerged(HandlerTestBase):
    """Merged tests from the newer resolve_deps suite."""

    def setup_method(self):
        super().setup_method()
        self.handler_func = resolve_handler
        self.filter_func = filter_func

    def test_filter_accepts_needs_resolution(self):
        envelope = self.create_envelope(
            deps=["identity:test_peer_id"],
            deps_included_and_valid=False
        )
        assert self.filter_func(envelope) is True
        envelope = self.create_envelope(event_ciphertext=b"..", event_key_id="k1")
        assert self.filter_func(envelope) is True

    def test_filter_rejects_already_resolved(self):
        envelope = self.create_envelope(
            deps=["identity:test_peer_id"],
            deps_included_and_valid=True
        )
        assert self.filter_func(envelope) is False

    def test_filter_rejects_no_deps(self):
        envelope = self.create_envelope()
        assert self.filter_func(envelope) is False

    def test_process_no_deps_needed(self):
        envelope = self.create_envelope(
            deps=[],
            event_id="test_event"
        )
        results = self.handler_func(envelope, self.db)
        assert len(results) == 1
        result = results[0]
        assert result['deps_included_and_valid'] is True
        assert result['resolved_deps'] == {}

    def test_process_resolves_transit_key_dep(self):
        envelope = self.create_envelope(
            deps=["transit_key:test_transit_key"],
            event_id="test_event"
        )
        results = self.handler_func(envelope, self.db)
        assert len(results) == 1
        result = results[0]
        assert result['deps_included_and_valid'] is True
        assert 'transit_key:test_transit_key' in result['resolved_deps']

    def test_process_handles_missing_deps(self):
        envelope = self.create_envelope(
            deps=["identity:missing_peer", "key:missing_key"],
            event_id="test_event"
        )
        results = self.handler_func(envelope, self.db)
        assert len(results) == 0
        row = self.db.execute(
            "SELECT * FROM blocked_events WHERE event_id = ?",
            ("test_event",)
        ).fetchone()
        assert row is not None
        deps = [r['dep_id'] for r in self.db.execute(
            "SELECT dep_id FROM blocked_event_deps WHERE event_id = ?",
            ("test_event",)
        )]
        assert set(deps) == {"missing_peer", "missing_key"}

    def test_process_partial_deps_resolution(self):
        envelope = self.create_envelope(
            deps=["transit_key:test_transit_key", "identity:missing_peer"],
            event_id="partial"
        )
        results = self.handler_func(envelope, self.db)
        assert results == []

    def test_process_handles_retry_count(self):
        envelope = self.create_envelope(
            deps=["identity:missing_peer"],
            event_id="test_event",
            retry_count=5
        )
        results = self.handler_func(envelope, self.db)
        assert results == []

    def test_parse_dep_ref(self):
        dep_type, dep_id = parse_dep_ref("identity:abc123")
        assert dep_type == "identity"
        assert dep_id == "abc123"
        dep_type, dep_id = parse_dep_ref("xyz789")
        assert dep_type == "event"
        assert dep_id == "xyz789"
        dep_type, dep_id = parse_dep_ref("key:group:main")
        assert dep_type == "key"
        assert dep_id == "group:main"
