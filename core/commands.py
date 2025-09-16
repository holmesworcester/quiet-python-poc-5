"""
Command registry for handler-defined commands.
"""
import sqlite3
from typing import Dict, List, Any, Callable


class CommandRegistry:
    """Registry for handler-defined commands."""

    def __init__(self) -> None:
        self._commands: Dict[str, Callable] = {}
        self._response_handlers: Dict[str, Callable] = {}
        self._envelope_reducers: Dict[str, Callable] = {}

    def register(self, name: str, command: Callable) -> None:
        """Register a command function."""
        self._commands[name] = command

    def register_response_handler(self, command_name: str, handler: Callable) -> None:
        """Register a response handler for a command."""
        self._response_handlers[command_name] = handler

    def register_envelope_reducer(self, command_name: str, reducer: Callable) -> None:
        """Register an envelope reducer for a command."""
        self._envelope_reducers[command_name] = reducer

    def execute(self, name: str, params: Dict[str, Any], db: sqlite3.Connection) -> List[dict[str, Any]]:
        """Execute a command and return emitted envelope."""
        if name not in self._commands:
            raise ValueError(f"Unknown command: {name}")

        command = self._commands[name]

        # Add db to params so commands can access it if needed
        params_with_db = params.copy()
        params_with_db['_db'] = db

        # Execute command with params (including _db)
        result = command(params_with_db)

        # Handle both single envelope and list of envelopes
        if isinstance(result, list):
            return result
        elif result:
            return [result]
        else:
            return []

    def get_response_handler(self, name: str) -> Callable | None:
        """Get the response handler for a command, if one exists."""
        return self._response_handlers.get(name)

    def get_envelope_reducer(self, name: str) -> Callable | None:
        """Get the envelope reducer for a command, if one exists."""
        return self._envelope_reducers.get(name)

    def list_commands(self) -> List[str]:
        """Return list of registered command names."""
        return sorted(self._commands.keys())

    def has_command(self, name: str) -> bool:
        """Check if a command is registered."""
        return name in self._commands


command_registry = CommandRegistry()