"""
Envelope type for carrying event-related data through handlers.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List


@dataclass
class Envelope:
    """
    Carries event-related data through the pipeline.
    Handlers add/modify attributes as the envelope flows through.
    """
    # Raw data from network
    origin_ip: Optional[str] = None
    origin_port: Optional[int] = None
    received_at: Optional[int] = None
    raw_data: Optional[bytes] = None
    
    # After transit decryption
    transit_key_id: Optional[str] = None
    transit_ciphertext: Optional[bytes] = None
    transit_plaintext: Optional[bytes] = None
    network_id: Optional[str] = None
    
    # Event layer
    event_key_id: Optional[str] = None
    event_ciphertext: Optional[bytes] = None
    event_plaintext: Optional[dict] = None
    event_id: Optional[str] = None  # blake2b hash of event ciphertext
    event_type: Optional[str] = None
    
    # Dependencies
    deps_included_and_valid: bool = False
    missing_deps: List[str] = field(default_factory=list)
    included_deps: Dict[str, 'Envelope'] = field(default_factory=dict)
    unblocked: bool = False
    
    # Validation states
    should_remove: Optional[bool] = None
    sig_checked: Optional[bool] = None
    is_group_member: Optional[bool] = None
    prevalidated: Optional[bool] = None
    validated: Optional[bool] = None
    projected: Optional[bool] = None
    
    # For created events
    self_created: Optional[bool] = None
    self_signed: Optional[bool] = None
    
    # For outgoing
    outgoing: Optional[bool] = None
    due_ms: Optional[int] = None
    address_id: Optional[str] = None
    user_id: Optional[str] = None
    peer_id: Optional[str] = None
    key_id: Optional[str] = None
    
    # Destination info
    dest_address: Optional[str] = None
    dest_port: Optional[int] = None
    outgoing_checked: Optional[bool] = None
    stripped_for_send: Optional[bool] = None
    
    # Errors/metadata
    error: Optional[str] = None
    retry_count: int = 0
    
    def __repr__(self):
        # Show only non-None fields for readability
        fields = []
        for k, v in self.__dict__.items():
            if v is not None and v != [] and v != {} and v != False:
                if isinstance(v, bytes):
                    fields.append(f"{k}=<bytes:{len(v)}>")
                elif isinstance(v, dict) and k == 'included_deps':
                    fields.append(f"{k}=<{len(v)} deps>")
                else:
                    fields.append(f"{k}={v!r}")
        return f"Envelope({', '.join(fields)})"