"""
Event Store Handler - wraps the event_store functions as a Handler class.
"""
from typing import List
import sqlite3
from core.handler import Handler
from core.types import Envelope
from . import event_store


class EventStoreHandler(Handler):
    """Handler that stores events in the database."""
    
    @property
    def name(self) -> str:
        return "event_store"
    
    def filter(self, envelope: Envelope) -> bool:
        """Use the existing filter function."""
        return event_store.filter_func(envelope)
    
    def process(self, envelope: Envelope, db: sqlite3.Connection) -> List[Envelope]:
        """Use the existing handler function."""
        result = event_store.handler(envelope, db)
        return [result] if result else []