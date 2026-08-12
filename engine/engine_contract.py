from typing import Any, Callable, Protocol, runtime_checkable
import inspect


@runtime_checkable
class EngineContract(Protocol):
    def init(self, **kwargs: Any) -> None:
        ...

    def chat(
        self,
        message: str,
        tools: Any = None,
        tool_executor: Callable[[str, dict], dict] | None = None,
        **kwargs: Any,
    ) -> str:
        ...


def validate_engine_contract(module: Any) -> None:
    """
    Valida el contrato minimo que debe cumplir cualquier engine cargado
    dinamicamente por el core.
    """
    init_fn = getattr(module, "init", None)
    chat_fn = getattr(module, "chat", None)

    if not callable(init_fn):
        raise TypeError("Engine contract violation: missing callable 'init(**params)'.")
    if not callable(chat_fn):
        raise TypeError("Engine contract violation: missing callable 'chat(message, tools=...)'.")

    chat_sig = inspect.signature(chat_fn)
    if len(chat_sig.parameters) < 1:
        raise TypeError("Engine contract violation: 'chat' must accept at least one argument ('message').")
