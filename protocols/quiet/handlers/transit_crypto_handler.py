"""
Transit Crypto Handler - wraps the transit_crypto functions as a Handler class.
"""
from typing import List
import sqlite3
from core.handler import Handler
from core.types import Envelope
from . import transit_crypto


class TransitCryptoHandler(Handler):
    """Handler that encrypts and decrypts transit messages."""
    
    @property
    def name(self) -> str:
        return "transit_crypto"
    
    def filter(self, envelope: Envelope) -> bool:
        """Use the existing filter function."""
        return transit_crypto.filter_func(envelope)
    
    def process(self, envelope: Envelope, db: sqlite3.Connection) -> List[Envelope]:
        """Use the existing handler function - no db needed."""
        result = transit_crypto.handler(envelope)
        return [result] if result else []