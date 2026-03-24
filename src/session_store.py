"""Persistência de sessões partilhada entre UI e API."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any

from . import config

_LOCK = Lock()


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
    }


def _normalize_sessions(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, list):
        return []
    out: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        session = {
            "id": str(item.get("id") or new_session()["id"]),
            "title": str(item.get("title") or "Nova sessão"),
            "messages": item.get("messages") if isinstance(item.get("messages"), list) else [],
            "created_at": str(item.get("created_at") or _now_iso()),
            "updated_at": str(item.get("updated_at") or item.get("created_at") or _now_iso()),
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
    return True
