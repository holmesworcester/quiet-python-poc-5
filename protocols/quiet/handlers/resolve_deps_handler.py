"""
Resolve Dependencies Handler - wraps the resolve_deps functions as a Handler class.
"""
from typing import List
import sqlite3
from core.handler import Handler
from core.types import Envelope
from . import resolve_deps


class ResolveDepsHandler(Handler):
    """Handler that resolves dependencies and unblocks waiting events."""
    
    @property
    def name(self) -> str:
        return "resolve_deps"
    
    def filter(self, envelope: Envelope) -> bool:
        """Use the existing filter function."""
        return resolve_deps.filter_func(envelope)
    
    def process(self, envelope: Envelope, db: sqlite3.Connection) -> List[Envelope]:
        """Use the existing handler function."""
        return resolve_deps.handler(envelope, db)