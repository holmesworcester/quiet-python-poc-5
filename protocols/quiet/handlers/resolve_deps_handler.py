"""
Handler that resolves dependencies for events.
"""
import json
from typing import List, Dict, Any, Optional
import sqlite3
from core.handler import Handler
from core.types import Envelope, validate_envelope_fields


class ResolveDepsHandler(Handler):
    """
    Resolves dependencies for events that need them.
    Consumes: envelopes where deps_included_and_valid is False or unblocked is True
    Emits: envelopes with missing_deps list OR deps_included_and_valid=True with included deps
    """
    
    @property 
    def name(self) -> str:
        return "resolve_deps"
    
    def filter(self, envelope: Envelope) -> bool:
        """Process envelopes that need dependency resolution."""
        return (
            validate_envelope_fields(envelope, {'event_plaintext'}) and
            (not envelope.get('deps_included_and_valid', False) or envelope.get('unblocked', False))
        )
    
    def process(self, envelope: Envelope, db: sqlite3.Connection) -> List[Envelope]:
        """Resolve dependencies from validated events."""
        
        # If no event data yet, can't resolve deps
        if not envelope.get('event_plaintext'):
            return []
        
        # Extract dependency IDs from event
        deps_needed = self._extract_deps(envelope['event_plaintext'])
        
        if not deps_needed:
            # No dependencies needed
            envelope['deps_included_and_valid'] = True
            envelope['missing_deps'] = []
            return [envelope]
        
        # Try to resolve each dependency
        resolved_deps = {}
        missing_deps = []
        
        for dep_id in deps_needed:
            dep_data = self._fetch_validated_event(dep_id, db)
            if dep_data:
                # Create envelope for the dependency
                dep_envelope = self._event_to_envelope(dep_data)
                resolved_deps[dep_id] = dep_envelope
            else:
                missing_deps.append(dep_id)
        
        if missing_deps:
            # Still have missing dependencies
            envelope['missing_deps'] = missing_deps
            envelope['deps_included_and_valid'] = False
            
            # Record what we're blocked by
            if envelope.get('event_id'):
                self._record_blocked(envelope['event_id'], missing_deps, db)
            
            return [envelope]
        else:
            # All dependencies resolved
            envelope['included_deps'] = resolved_deps
            envelope['missing_deps'] = []
            envelope['deps_included_and_valid'] = True
            return [envelope]
    
    def _extract_deps(self, event_data: Dict[str, Any]) -> List[str]:
        """Extract dependency IDs from event data."""
        deps = []
        event_type = event_data.get('type')
        
        # Identity events have no dependencies
        if event_type == 'identity':
            return []
        
        # Transit secret events only depend on the peer_id
        if event_type == 'transit_secret':
            if 'peer_id' in event_data:
                deps.append(event_data['peer_id'])
            return deps
            
        # Key events only depend on the peer_id
        if event_type == 'key':
            if 'peer_id' in event_data:
                deps.append(event_data['peer_id'])
            return deps
        
        # Different event types have different dependency fields
        if 'depends_on' in event_data:
            deps.extend(event_data['depends_on'])
        
        # For events that use keys (not key events themselves)
        if 'event_key_id' in event_data:
            deps.append(event_data['event_key_id'])
            
        if 'transit_key_id' in event_data:
            deps.append(event_data['transit_key_id'])
            
        if 'peer_id' in event_data:
            deps.append(event_data['peer_id'])
            
        return deps
    
    def _fetch_validated_event(self, event_id: str, db: sqlite3.Connection) -> Optional[Dict[str, Any]]:
        """Fetch a validated event from the database."""
        cursor = db.execute(
            "SELECT event_data, event_type FROM events WHERE event_id = ?",
            (event_id,)
        )
        row = cursor.fetchone()
        if row:
            data = json.loads(row['event_data'])
            data['_event_type'] = row['event_type']
            return data
        return None
    
    def _event_to_envelope(self, event_data: Dict[str, Any]) -> Envelope:
        """Convert stored event data back to envelope."""
        envelope: Envelope = {
            'event_plaintext': event_data,
            'event_type': event_data.get('_event_type'),
            'validated': True
        }
        return envelope
    
    def _record_blocked(self, event_id: str, missing_deps: List[str], db: sqlite3.Connection):
        """Record that an event is blocked by missing dependencies."""
        for dep_id in missing_deps:
            db.execute(
                "INSERT OR IGNORE INTO blocked_by (blocked_event_id, blocking_event_id) VALUES (?, ?)",
                (event_id, dep_id)
            )
        db.commit()