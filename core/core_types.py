"""
Protocol-agnostic base types for the core framework.

This module defines the fundamental types used by the framework without any
protocol-specific knowledge. Protocols extend these types with their own fields.
"""

from typing import TypedDict, Protocol, runtime_checkable, TypeVar, Any, Generic
from collections.abc import Callable


# The framework doesn't define envelope structure at all.
# Envelopes are just dicts that protocols define.
# The framework only passes them through handlers.


# The framework doesn't define delta structure either.
# Deltas are just dicts that the protocol's projectors return.
# The framework passes them to the database layer.


@runtime_checkable
class CommandFunc(Protocol):
    """Protocol for event creation commands"""
    def __call__(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Create an event envelope from parameters.

        The framework doesn't care about the structure,
        just that it returns a dict.
        """
        ...


@runtime_checkable
class ValidatorFunc(Protocol):
    """Protocol for event validators"""
    def __call__(self, envelope: dict[str, Any]) -> bool:
        """
        Validate an envelope.

        The framework only cares about the boolean result.
        """
        ...


@runtime_checkable
class ProjectorFunc(Protocol):
    """Protocol for event projectors"""
    def __call__(self, envelope: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Convert envelope to database deltas.

        The framework doesn't care about delta structure,
        just that it's a list of dicts.
        """
        ...


@runtime_checkable
class HandlerFunc(Protocol):
    """Protocol for pipeline handlers"""
    def __call__(self, envelope: dict[str, Any]) -> dict[str, Any] | None:
        """
        Process envelope and return transformed envelope.

        Returns None if envelope should be dropped.
        """
        ...


@runtime_checkable
class FilterFunc(Protocol):
    """Protocol for handler filter functions"""
    def __call__(self, envelope: dict[str, Any]) -> bool:
        """
        Determine if handler should process this envelope.
        """
        ...


class HandlerDef(TypedDict):
    """Handler definition with filter and handler function"""
    name: str
    filter: FilterFunc
    handler: HandlerFunc


def command(func: Callable[[dict[str, Any]], Any]) -> Callable[[dict[str, Any]], Any]:
    """
    Decorator to mark command functions.

    The framework only validates that it takes and returns dicts.
    Protocol-specific validation is done by the protocol.
    """
    import functools
    import inspect

    sig = inspect.signature(func)
    params = list(sig.parameters.keys())

    if len(params) != 1:
        raise TypeError(
            f"{func.__name__} must have exactly one parameter, got {len(params)}"
        )

    @functools.wraps(func)
    def wrapper(params: dict[str, Any]) -> dict[str, Any] | list[dict[str, Any]]:
        if not isinstance(params, dict):
            raise TypeError(f"Expected dict for params, got {type(params).__name__}")

        result = func(params)

        # Handle both single envelope and list of envelopes
        if not isinstance(result, (dict, list)):
            raise TypeError(f"{func.__name__} must return dict or list[dict], got {type(result).__name__}")

        if isinstance(result, list):
            for i, env in enumerate(result):
                if not isinstance(env, dict):
                    raise TypeError(f"{func.__name__} envelope[{i}] must be dict, got {type(env).__name__}")

        return result

    wrapper._is_command = True  # type: ignore

    # Auto-register the command
    from core.commands import command_registry
    command_registry.register(func.__name__, wrapper)

    return wrapper


def validator(func: Callable[[dict[str, Any]], bool]) -> Callable[[dict[str, Any]], bool]:
    """
    Decorator to mark validator functions.

    The framework only validates the signature and return type.
    """
    import functools
    import inspect

    sig = inspect.signature(func)
    params = list(sig.parameters.keys())

    if len(params) != 1:
        raise TypeError(
            f"{func.__name__} must have exactly one parameter, got {len(params)}"
        )

    @functools.wraps(func)
    def wrapper(envelope: dict[str, Any]) -> bool:
        if not isinstance(envelope, dict):
            raise TypeError(f"Expected dict for envelope, got {type(envelope).__name__}")

        result = func(envelope)

        if not isinstance(result, bool):
            raise TypeError(f"{func.__name__} must return bool, got {type(result).__name__}")

        return result

    wrapper._is_validator = True  # type: ignore
    return wrapper


def projector(func: Callable[[dict[str, Any]], list[dict[str, Any]]]) -> Callable[[dict[str, Any]], list[dict[str, Any]]]:
    """
    Decorator to mark projector functions.

    The framework only validates that it returns a list of dicts.
    """
    import functools
    import inspect

    sig = inspect.signature(func)
    params = list(sig.parameters.keys())

    if len(params) != 1:
        raise TypeError(
            f"{func.__name__} must have exactly one parameter, got {len(params)}"
        )

    @functools.wraps(func)
    def wrapper(envelope: dict[str, Any]) -> list[dict[str, Any]]:
        if not isinstance(envelope, dict):
            raise TypeError(f"Expected dict for envelope, got {type(envelope).__name__}")

        result = func(envelope)

        if not isinstance(result, list):
            raise TypeError(f"{func.__name__} must return list, got {type(result).__name__}")

        for i, delta in enumerate(result):
            if not isinstance(delta, dict):
                raise TypeError(f"{func.__name__} delta[{i}] must be dict, got {type(delta).__name__}")

        return result

    wrapper._is_projector = True  # type: ignore
    return wrapper


def handler(name: str, filter_func: FilterFunc) -> Callable[[Callable[[dict[str, Any]], dict[str, Any] | None]], HandlerDef]:
    """
    Decorator to mark handler functions.
    """
    def decorator(func: Callable[[dict[str, Any]], dict[str, Any] | None]) -> HandlerDef:
        return {
            "name": name,
            "filter": filter_func,
            "handler": func  # type: ignore
        }
    return decorator


def command_response(func: Callable[[str, list[dict[str, Any]], Any], dict[str, Any]]) -> Callable[[str, list[dict[str, Any]], Any], dict[str, Any]]:
    """
    Decorator to mark command response handlers.

    Response handlers run after pipeline processing completes and have access to:
    - request_id: The unique request identifier
    - envelopes: All processed envelopes from this request
    - db: Database connection for running follow-up queries
    """
    import functools
    import inspect

    sig = inspect.signature(func)
    params = list(sig.parameters.keys())

    if len(params) != 3:
        raise TypeError(
            f"{func.__name__} must have exactly 3 parameters (request_id, envelopes, db), got {len(params)}"
        )

    @functools.wraps(func)
    def wrapper(request_id: str, envelopes: list[dict[str, Any]], db: Any) -> dict[str, Any]:
        if not isinstance(request_id, str):
            raise TypeError(f"Expected str for request_id, got {type(request_id).__name__}")

        if not isinstance(envelopes, list):
            raise TypeError(f"Expected list for envelopes, got {type(envelopes).__name__}")

        result = func(request_id, envelopes, db)

        if not isinstance(result, dict):
            raise TypeError(f"{func.__name__} must return dict, got {type(result).__name__}")

        return result

    wrapper._is_command_response = True  # type: ignore
    return wrapper


def response_handler(command_name: str):
    """
    Decorator to register a response handler for a command.

    Response handlers shape the API response after pipeline processing.
    They have access to:
    - stored_ids: Dict of event_type -> event_id for stored events
    - params: Original command parameters
    - db: Database connection for running queries
    """
    def decorator(func: Callable[[dict[str, str], dict[str, Any], Any], dict[str, Any]]) -> Callable:
        import functools
        import inspect

        sig = inspect.signature(func)
        params_list = list(sig.parameters.keys())

        if len(params_list) != 3:
            raise TypeError(
                f"{func.__name__} must have exactly 3 parameters (stored_ids, params, db), got {len(params_list)}"
            )

        @functools.wraps(func)
        def wrapper(stored_ids: dict[str, str], params: dict[str, Any], db: Any) -> dict[str, Any]:
            if not isinstance(stored_ids, dict):
                raise TypeError(f"Expected dict for stored_ids, got {type(stored_ids).__name__}")

            if not isinstance(params, dict):
                raise TypeError(f"Expected dict for params, got {type(params).__name__}")

            result = func(stored_ids, params, db)

            if not isinstance(result, dict):
                raise TypeError(f"{func.__name__} must return dict, got {type(result).__name__}")

            return result

        # Auto-register the response handler
        from core.commands import command_registry
        command_registry.register_response_handler(command_name, wrapper)

        return wrapper

    return decorator


def envelope_reducer(func: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]) -> Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]:
    """
    Decorator to mark envelope reducer functions.

    Reducers process a stream of envelopes and reduce them to summary data.
    Used by commands that generate many envelopes to avoid storing all of them.

    Takes:
    - accumulator: The current accumulated state (empty dict on first call)
    - envelope: The current envelope being processed

    Returns:
    - Updated accumulator
    """
    import functools
    import inspect

    sig = inspect.signature(func)
    params = list(sig.parameters.keys())

    if len(params) != 2:
        raise TypeError(
            f"{func.__name__} must have exactly 2 parameters (accumulator, envelope), got {len(params)}"
        )

    @functools.wraps(func)
    def wrapper(accumulator: dict[str, Any], envelope: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(accumulator, dict):
            raise TypeError(f"Expected dict for accumulator, got {type(accumulator).__name__}")

        if not isinstance(envelope, dict):
            raise TypeError(f"Expected dict for envelope, got {type(envelope).__name__}")

        result = func(accumulator, envelope)

        if not isinstance(result, dict):
            raise TypeError(f"{func.__name__} must return dict, got {type(result).__name__}")

        return result

    wrapper._is_envelope_reducer = True  # type: ignore
    return wrapper