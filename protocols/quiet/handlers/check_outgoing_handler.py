"""
Check Outgoing Handler - wraps the check_outgoing functions as a Handler class.
"""
from typing import List
import sqlite3
from core.handler import Handler
from core.types import Envelope
from . import check_outgoing


class CheckOutgoingHandler(Handler):
    """Handler that checks outgoing messages have proper transit keys."""
    
    @property
    def name(self) -> str:
        return "check_outgoing"
    
    def filter(self, envelope: Envelope) -> bool:
        """Use the existing filter function."""
        return check_outgoing.filter_func(envelope)
    
    def process(self, envelope: Envelope, db: sqlite3.Connection) -> List[Envelope]:
        """Use the existing handler function - no db needed."""
        result = check_outgoing.handler(envelope)
        return [result] if result else []