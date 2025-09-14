"""
Remove Handler - wraps the remove functions as a Handler class.
"""
from typing import List
import sqlite3
from core.handler import Handler
from core.types import Envelope
from . import remove


class RemoveHandler(Handler):
    """Handler that processes remove events."""
    
    @property
    def name(self) -> str:
        return "remove"
    
    def filter(self, envelope: Envelope) -> bool:
        """Use the existing filter function."""
        return remove.filter_func(envelope)
    
    def process(self, envelope: Envelope, db: sqlite3.Connection) -> List[Envelope]:
        """Use the existing handler function."""
        result = remove.handler(envelope, db)
        return [result] if result else []