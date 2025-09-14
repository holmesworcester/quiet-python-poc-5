"""
Event Crypto Handler - wraps the event_crypto functions as a Handler class.
"""
from typing import List
import sqlite3
from core.handler import Handler
from core.types import Envelope
from . import event_crypto


class EventCryptoHandler(Handler):
    """Handler that encrypts and decrypts events."""
    
    @property
    def name(self) -> str:
        return "event_crypto"
    
    def filter(self, envelope: Envelope) -> bool:
        """Use the existing filter function."""
        return event_crypto.filter_func(envelope)
    
    def process(self, envelope: Envelope, db: sqlite3.Connection) -> List[Envelope]:
        """Use the existing handler function - no db needed."""
        result = event_crypto.handler(envelope)
        return [result] if result else []