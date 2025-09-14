"""
Membership Check Handler - wraps the membership_check functions as a Handler class.
"""
from typing import List
import sqlite3
from core.handler import Handler
from core.types import Envelope
from . import membership_check


class MembershipCheckHandler(Handler):
    """Handler that checks group membership for events."""
    
    @property
    def name(self) -> str:
        return "membership_check"
    
    def filter(self, envelope: Envelope) -> bool:
        """Use the existing filter function."""
        return membership_check.filter_func(envelope)
    
    def process(self, envelope: Envelope, db: sqlite3.Connection) -> List[Envelope]:
        """Use the existing handler function - no db needed."""
        result = membership_check.handler(envelope)
        return [result] if result else []