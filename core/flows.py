"""
Core flow helpers for readable orchestrations.

Flows should:
- Query via query registry (read-only)
- Emit events via the pipeline runner (no commands registry)
- Return a result dict

They must not write to the DB directly.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Callable, List, Tuple
import sqlite3

from core.db import ReadOnlyConnection


@dataclass
class FlowCtx:
    db: sqlite3.Connection
    runner: Any
    protocol_dir: str
    request_id: str

    @staticmethod
    def from_params(params: Dict[str, Any]) -> "FlowCtx":
        db = params.get('_db')
        runner = params.get('_runner')
        protocol_dir = params.get('_protocol_dir')
        request_id = params.get('_request_id')
        if not (db and runner and protocol_dir and request_id):
            raise ValueError("FlowCtx missing required context (_db, _runner, _protocol_dir, _request_id)")
        return FlowCtx(db=db, runner=runner, protocol_dir=str(protocol_dir), request_id=str(request_id))

    def query(self, query_id: str, params: Optional[Dict[str, Any]] = None) -> Any:
        return query(self, query_id, params)

    # New pattern: emit an event directly (no separate create command)
    def emit_event(
        self,
        event_type: str,
        data: Dict[str, Any],
        *,
        by: Optional[str] = None,
        deps: Optional[List[str]] = None,
        network_id: Optional[str] = None,
        local_only: bool = False,
        seal_to: Optional[str] = None,
        encrypt_to: Optional[str] = None,
        self_created: bool = True,
        is_outgoing: bool = False,
    ) -> str:
        env: Dict[str, Any] = {
            'event_plaintext': {'type': event_type, **data},
            'event_type': event_type,
            'self_created': bool(self_created),
        }
        if by:
            # Use peer_id for signing context by default
            env['peer_id'] = by
        # Always include deps array; empty means no deps and will be marked valid
        env['deps'] = list(deps) if deps else []
        if network_id:
            env['network_id'] = network_id
        if local_only:
            env['local_only'] = True
        if seal_to:
            env['seal_to'] = seal_to
        if encrypt_to:
            env['encrypt_to'] = encrypt_to
        if is_outgoing:
            env['is_outgoing'] = True

        # Run through the pipeline and return the resulting event id
        env['request_id'] = self.request_id
        ids = self.runner.run(protocol_dir=self.protocol_dir, input_envelopes=[env], db=self.db)
        # Prefer id keyed by event_type
        if event_type in ids:
            return ids[event_type]
        # Fallback: infer id when only one id exists
        if len(ids) == 1:
            return next(iter(ids.values()))
        raise ValueError(f"emit_event did not produce a stored id for {event_type}: ids={ids}")


def query(ctx: FlowCtx, query_id: str, params: Optional[Dict[str, Any]] = None) -> Any:
    """
    Execute a read-only query via query registry.
    """
    from core.queries import query_registry
    return query_registry.execute(query_id, params or {}, ReadOnlyConnection(ctx.db))




class FlowRegistry:
    """Registry for API flows (operation-like functions)."""

    def __init__(self) -> None:
        self._flows: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {}

    def register(self, op_id: str, func: Callable[[Dict[str, Any]], Dict[str, Any]]) -> None:
        self._flows[op_id] = func

    def has_flow(self, op_id: str) -> bool:
        return op_id in self._flows

    def execute(self, op_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if op_id not in self._flows:
            raise ValueError(f"Unknown flow op: {op_id}")
        return self._flows[op_id](params)

    def list_flows(self) -> List[str]:
        return sorted(self._flows.keys())

    def alias(self, alias_id: str, target_id: str) -> None:
        """Register an alias for an existing flow operation."""
        if target_id not in self._flows:
            # Allow aliasing to be deferred: it can be re-applied later if needed
            # For now, raise to surface missing target during discovery
            raise ValueError(f"Cannot alias '{alias_id}' to missing flow '{target_id}'")
        self._flows[alias_id] = self._flows[target_id]


flows_registry = FlowRegistry()


def flow_op(op_id: Optional[str] = None) -> Callable[[Callable[[Dict[str, Any]], Dict[str, Any]]], Callable[[Dict[str, Any]], Dict[str, Any]]]:
    """
    Decorator to register a flow function as an API operation.

    If op_id is not provided, derive it as '<event>.<func_name>' from the module path
    'protocols.<protocol>.events.<event>.flows'.
    """
    def decorator(func: Callable[[Dict[str, Any]], Dict[str, Any]]) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
        nonlocal op_id
        if op_id is None:
            parts = func.__module__.split('.')
            # Expect: ['protocols', '<protocol>', 'events', '<event>', 'flows']
            event = parts[3] if len(parts) >= 5 else func.__name__
            op_id = f"{event}.{func.__name__}"
        flows_registry.register(op_id, func)
        return func

    return decorator
