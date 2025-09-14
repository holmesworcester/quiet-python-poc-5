"""
Send to Network Handler - wraps the send_to_network functions as a Handler class.
"""
from typing import List
import sqlite3
from core.handler import Handler
from core.types import Envelope
from . import send_to_network


class SendToNetworkHandler(Handler):
    """Terminal handler that sends envelopes to the network."""
    
    @property
    def name(self) -> str:
        return "send_to_network"
    
    def filter(self, envelope: Envelope) -> bool:
        """Use the existing filter function."""
        return send_to_network.filter_func(envelope)
    
    def process(self, envelope: Envelope, db: sqlite3.Connection) -> List[Envelope]:
        """Use the existing handler function - terminal handler returns None."""
        # TODO: Get send_func from somewhere - for now just log
        def send_func(envelope):
            print(f"[send_to_network] Would send envelope to network: {envelope.get('event_id', 'unknown')}")
        
        send_to_network.handler(envelope, send_func)
        return []  # Terminal handler