"""Persistência de sessões e respostas guardadas."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any

from . import config

_LOCK = Lock()
_SAVED_LOCK = Lock()


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def new_session(*, title: str = "Nova sessão") -> dict[str, Any]:
    now = datetime.now()
    return {
        "id": now.strftime("%Y%m%d%H%M%S%f"),
        "title": title,
        "messages": [],
        "created_at": now.isoformat(timespec="seconds"),
        "updated_at": now.isoformat(timespec="seconds"),
        "active_source_id": None,
        "active_source_title": None,
    }


def _normalize_message(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    role = str(item.get("role") or "assistant")
    if role not in {"user", "assistant"}:
        role = "assistant"
    normalized = {
        "role": role,
        "content": str(item.get("content") or ""),
    }
    created_at = str(item.get("created_at") or "").strip()
    if created_at:
        normalized["created_at"] = created_at
    qa_result = item.get("qa_result")
    if isinstance(qa_result, dict):
        normalized["qa_result"] = qa_result
    return normalized


def _normalize_sessions(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, list):
        return []
    out: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        raw_messages = item.get("messages") if isinstance(item.get("messages"), list) else []
        messages = [message for message in (_normalize_message(entry) for entry in raw_messages) if message]
        session = {
            "id": str(item.get("id") or new_session()["id"]),
            "title": str(item.get("title") or "Nova sessão"),
            "messages": messages,
            "created_at": str(item.get("created_at") or _now_iso()),
            "updated_at": str(item.get("updated_at") or item.get("created_at") or _now_iso()),
            "active_source_id": str(item.get("active_source_id") or "").strip() or None,
            "active_source_title": str(item.get("active_source_title") or "").strip() or None,
        }
        out.append(session)
    return out


def load_sessions() -> list[dict[str, Any]]:
    config.ensure_directories()
    path = config.SESSIONS_FILE
    if not path.exists():
        return []
    with _LOCK:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
    return _normalize_sessions(raw)


def save_sessions(sessions: list[dict[str, Any]]) -> None:
    config.ensure_directories()
    path = config.SESSIONS_FILE
    normalized = _normalize_sessions(sessions)
    payload = json.dumps(normalized, ensure_ascii=False, indent=2)
    tmp = Path(f"{path}.tmp")
    with _LOCK:
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(path)


def list_sessions() -> list[dict[str, Any]]:
    sessions = load_sessions()
    return sorted(sessions, key=lambda s: (s.get("updated_at") or "", s.get("created_at") or ""), reverse=True)


def get_session(session_id: str) -> dict[str, Any] | None:
    for session in load_sessions():
        if str(session.get("id")) == str(session_id):
            return session
    return None


def upsert_session(session: dict[str, Any]) -> dict[str, Any]:
    sessions = load_sessions()
    session = {
        **session,
        "updated_at": _now_iso(),
        "created_at": str(session.get("created_at") or _now_iso()),
    }
    replaced = False
    for idx, existing in enumerate(sessions):
        if str(existing.get("id")) == str(session.get("id")):
            sessions[idx] = session
            replaced = True
            break
    if not replaced:
        sessions.append(session)
    save_sessions(sessions)
    return session


def create_session(*, title: str = "Nova sessão") -> dict[str, Any]:
    session = new_session(title=title)
    return upsert_session(session)


def delete_session(session_id: str) -> bool:
    sessions = load_sessions()
    remaining = [s for s in sessions if str(s.get("id")) != str(session_id)]
    if len(remaining) == len(sessions):
        return False
    save_sessions(remaining)
    # Limpa também as respostas guardadas que referenciam este chat
    _purge_saved_for_session(session_id)
    return True


# ─── Respostas guardadas (unificação: backend em vez de localStorage) ─────────

def _load_saved_raw() -> list[dict[str, Any]]:
    config.ensure_directories()
    path = config.SAVED_RESPONSES_FILE
    if not path.exists():
        return []
    with _SAVED_LOCK:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return raw if isinstance(raw, list) else []
        except Exception:
            return []


def _save_saved_raw(items: list[dict[str, Any]]) -> None:
    config.ensure_directories()
    path = config.SAVED_RESPONSES_FILE
    payload = json.dumps(items, ensure_ascii=False, indent=2)
    tmp = Path(f"{path}.tmp")
    with _SAVED_LOCK:
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(path)


def list_saved_responses() -> list[dict[str, Any]]:
    items = _load_saved_raw()
    # Mantém apenas respostas cujo chat ainda existe
    existing_ids = {str(s.get("id")) for s in load_sessions()}
    valid = [item for item in items if str(item.get("session_id", "")) in existing_ids]
    if len(valid) != len(items):
        _save_saved_raw(valid)
    return valid


def add_saved_response(item: dict[str, Any]) -> dict[str, Any]:
    key = str(item.get("key") or "")
    if not key:
        return item
    items = _load_saved_raw()
    # Remove duplicado se existir
    items = [i for i in items if str(i.get("key", "")) != key]
    item = {**item, "saved_at": _now_iso()}
    items = [item] + items
    # Limita a 50 guardados
    _save_saved_raw(items[:50])
    return item


def remove_saved_response(key: str) -> bool:
    items = _load_saved_raw()
    remaining = [i for i in items if str(i.get("key", "")) != key]
    if len(remaining) == len(items):
        return False
    _save_saved_raw(remaining)
    return True


def _purge_saved_for_session(session_id: str) -> None:
    """Remove automaticamente guardados que referenciam um chat apagado."""
    items = _load_saved_raw()
    remaining = [i for i in items if str(i.get("session_id", "")) != str(session_id)]
    if len(remaining) != len(items):
        _save_saved_raw(remaining)
