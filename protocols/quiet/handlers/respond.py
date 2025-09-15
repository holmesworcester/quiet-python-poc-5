"""Respond handler - executes event-triggered responder functions."""

import sqlite3
import time
from typing import Dict, List, Any
from core.handlers import Handler


class RespondHandler(Handler):
    """Executes responder functions in response to events."""

    @property
    def name(self) -> str:
        return "respond"

    def __init__(self):
        super().__init__()
        self.responders = self._load_responders()

    def _load_responders(self) -> Dict[str, callable]:
        """Dynamically load all responder functions from event directories."""
        import os
        import importlib
        from pathlib import Path

        responders = {}

        # Find the events directory
        events_dir = Path(__file__).parent.parent / 'events'

        if not events_dir.exists():
            return responders

        # Scan each event type directory for responder.py
        for event_dir in events_dir.iterdir():
            if not event_dir.is_dir():
                continue

            responder_file = event_dir / 'responder.py'
            if not responder_file.exists():
                continue

            # Import the responder module
            event_type = event_dir.name
            module_name = f'protocols.quiet.events.{event_type}.responder'

            try:
                module = importlib.import_module(module_name)

                # Look for functions that end with _responder
                for attr_name in dir(module):
                    if attr_name.endswith('_responder') and not attr_name.startswith('_'):
                        responder_fn = getattr(module, attr_name)
                        if callable(responder_fn):
                            # Map the event type to the responder
                            responders[event_type] = responder_fn
                            # print(f"[ReflectHandler] Loaded responder: {event_type} -> {attr_name}")
            except Exception as e:
                print(f"[ReflectHandler] Failed to load responder from {module_name}: {e}")

        return responders

    def filter(self, envelope: Dict[str, Any]) -> bool:
        """Process validated events that have responders."""
        event_type = envelope.get('event_type')
        # Only process incoming, validated events (not our outgoing ones)
        return (event_type in self.responders and
                envelope.get('validated') and
                not envelope.get('is_outgoing') and
                envelope.get('event_plaintext'))

    def process(self, envelope: Dict[str, Any], db: sqlite3.Connection) -> List[Dict[str, Any]]:
        """Execute the appropriate responder."""
        event_type = envelope['event_type']
        responder_fn = self.responders[event_type]
        time_now_ms = int(time.time() * 1000)


        # Run the responder (responders get read-only access)
        try:
            success, envelopes = responder_fn(envelope, db, time_now_ms)
        except Exception as e:
            print(f"[RespondersHandler] Responder for {event_type} failed: {e}")
            return []

        if success:
            print(f"[RespondersHandler] Responder for {event_type} succeeded, emitting {len(envelopes)} envelopes")
            return envelopes
        else:
            print(f"[RespondersHandler] Responder for {event_type} returned failure")
            return []