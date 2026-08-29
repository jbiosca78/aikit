from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List
import json


Message = Dict[str, Any]


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


@dataclass
class HistoryConfig:
    backend: str = "memory"  # memory | json
    path: str = "data/history.json"
    max_messages_per_conversation: int = 200


class HistoryStore:
    def list_conversations(self, principal_id: str) -> List[str]:
        raise NotImplementedError

    def get_messages(self, principal_id: str, conversation_id: str) -> List[Message]:
        raise NotImplementedError

    def append_messages(self, principal_id: str, conversation_id: str, messages: List[Message]) -> None:
        raise NotImplementedError


class MemoryHistoryStore(HistoryStore):
    def __init__(self, max_messages_per_conversation: int = 200):
        self._data: Dict[str, Dict[str, List[Message]]] = {}
        self._max_messages = max(1, int(max_messages_per_conversation))
        self._lock = RLock()

    def _get_conv(self, principal_id: str, conversation_id: str) -> List[Message]:
        by_user = self._data.setdefault(principal_id, {})
        return by_user.setdefault(conversation_id, [])

    def list_conversations(self, principal_id: str) -> List[str]:
        with self._lock:
            return sorted(list(self._data.get(principal_id, {}).keys()))

    def get_messages(self, principal_id: str, conversation_id: str) -> List[Message]:
        with self._lock:
            return list(self._get_conv(principal_id, conversation_id))

    def append_messages(self, principal_id: str, conversation_id: str, messages: List[Message]) -> None:
        if not messages:
            return
        with self._lock:
            conv = self._get_conv(principal_id, conversation_id)
            conv.extend(messages)
            if len(conv) > self._max_messages:
                del conv[: len(conv) - self._max_messages]


class JsonFileHistoryStore(HistoryStore):
    def __init__(self, path: str, max_messages_per_conversation: int = 200):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._max_messages = max(1, int(max_messages_per_conversation))
        self._lock = RLock()
        if not self._path.exists():
            self._write_all({})

    def _read_all(self) -> Dict[str, Dict[str, List[Message]]]:
        with self._lock:
            try:
                raw = self._path.read_text(encoding="utf-8")
                parsed = json.loads(raw) if raw.strip() else {}
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                return {}
            return {}

    def _write_all(self, data: Dict[str, Dict[str, List[Message]]]) -> None:
        with self._lock:
            self._path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def list_conversations(self, principal_id: str) -> List[str]:
        data = self._read_all()
        by_user = data.get(principal_id, {})
        if not isinstance(by_user, dict):
            return []
        return sorted(list(by_user.keys()))

    def get_messages(self, principal_id: str, conversation_id: str) -> List[Message]:
        data = self._read_all()
        by_user = data.get(principal_id, {})
        if not isinstance(by_user, dict):
            return []
        conv = by_user.get(conversation_id, [])
        if not isinstance(conv, list):
            return []
        return list(conv)

    def append_messages(self, principal_id: str, conversation_id: str, messages: List[Message]) -> None:
        if not messages:
            return
        data = self._read_all()
        by_user = data.setdefault(principal_id, {})
        if not isinstance(by_user, dict):
            by_user = {}
            data[principal_id] = by_user
        conv = by_user.setdefault(conversation_id, [])
        if not isinstance(conv, list):
            conv = []
            by_user[conversation_id] = conv

        for msg in messages:
            role = _safe_text(msg.get("role", ""))
            content = _safe_text(msg.get("content", ""))
            if not role:
                continue
            conv.append({"role": role, "content": content})

        if len(conv) > self._max_messages:
            del conv[: len(conv) - self._max_messages]

        self._write_all(data)


def build_history_store(cfg: Dict[str, Any]) -> HistoryStore:
    hist_cfg = cfg.get("history", {}) if isinstance(cfg, dict) else {}
    backend = str(hist_cfg.get("backend", "memory")).strip().lower()
    max_messages = int(hist_cfg.get("max_messages_per_conversation", 200))

    if backend == "json":
        path = str(hist_cfg.get("path", "data/history.json")).strip() or "data/history.json"
        return JsonFileHistoryStore(path=path, max_messages_per_conversation=max_messages)

    return MemoryHistoryStore(max_messages_per_conversation=max_messages)
