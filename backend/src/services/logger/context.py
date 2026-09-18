import uuid
from contextvars import ContextVar, Token
from typing import Any, Dict, Optional

_current_trace_id: ContextVar[Optional[str]] = ContextVar("current_trace_id", default=None)
_journey_context: ContextVar[Dict[str, Any]] = ContextVar("journey_context", default={})


def generate_trace_id(prefix: str = "trc_") -> str:
    return f"{prefix}{uuid.uuid4().hex[:16]}"


def get_current_trace_id() -> Optional[str]:
    return _current_trace_id.get()


def set_current_trace_id(trace_id: str) -> Token:
    return _current_trace_id.set(trace_id)


def reset_trace_id(token: Token) -> None:
    _current_trace_id.reset(token)


def get_journey_context() -> Dict[str, Any]:
    return _journey_context.get().copy()


def set_journey_context(ctx: Dict[str, Any]) -> Token:
    return _journey_context.set(ctx.copy())


def update_journey_context(**kwargs) -> None:
    current = _journey_context.get().copy()
    current.update(kwargs)
    _journey_context.set(current)


def reset_journey_context(token: Token) -> None:
    _journey_context.reset(token)
