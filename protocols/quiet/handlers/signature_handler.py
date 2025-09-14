"""
Signature Handler - wraps the signature functions as a Handler class.
"""
from typing import List
import sqlite3
from core.handler import Handler
from core.types import Envelope
from . import signature


class SignatureHandler(Handler):
    """Handler that signs self-created events and verifies signatures."""
    
    @property
    def name(self) -> str:
        return "signature"
    
    def filter(self, envelope: Envelope) -> bool:
        """Process envelopes that need signing or signature verification."""
        return signature.filter_func(envelope)
    
    def process(self, envelope: Envelope, db: sqlite3.Connection) -> List[Envelope]:
        """Use the existing handler function - no db needed."""
        result = signature.handler(envelope)
        return [result] if result else []