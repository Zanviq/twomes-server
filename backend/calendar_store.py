"""내부 캘린더 저장소 — 사용자별 events.json.

이벤트 모델(CalenMate 호환):
  {id, title, description, start(ISO), end(ISO), allDay(bool), color}
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi import HTTPException

from .auth import SessionUser
from .config import Settings


def _events_path(user: SessionUser, settings: Settings) -> Path:
    base = settings.user_root(user.username) / "calendar"
    base.mkdir(parents=True, exist_ok=True)
    return base / "events.json"


def _load(user: SessionUser, settings: Settings) -> list[dict]:
    p = _events_path(user, settings)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save(events: list[dict], user: SessionUser, settings: Settings) -> None:
    _events_path(user, settings).write_text(
        json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def list_events(
    user: SessionUser, settings: Settings, frm: str | None = None, to: str | None = None
) -> list[dict]:
    events = _load(user, settings)
    if frm or to:
        result = []
        for e in events:
            start = e.get("start", "")
            if frm and start < frm:
                continue
            if to and start > to:
                continue
            result.append(e)
        return result
    return events


def create_event(user: SessionUser, settings: Settings, payload: dict) -> dict:
    events = _load(user, settings)
    event = {
        "id": uuid.uuid4().hex,
        "title": str(payload.get("title", "")).strip() or "(제목 없음)",
        "description": str(payload.get("description", "")),
        "start": payload["start"],
        "end": payload.get("end", payload["start"]),
        "allDay": bool(payload.get("allDay", False)),
        "color": payload.get("color", "2"),
    }
    events.append(event)
    _save(events, user, settings)
    return event


def update_event(user: SessionUser, settings: Settings, eid: str, payload: dict) -> dict:
    events = _load(user, settings)
    for e in events:
        if e["id"] == eid:
            for k in ("title", "description", "start", "end", "allDay", "color"):
                if k in payload and payload[k] is not None:
                    e[k] = payload[k]
            _save(events, user, settings)
            return e
    raise HTTPException(status_code=404, detail="이벤트를 찾을 수 없습니다.")


def delete_event(user: SessionUser, settings: Settings, eid: str) -> None:
    events = _load(user, settings)
    new = [e for e in events if e["id"] != eid]
    if len(new) == len(events):
        raise HTTPException(status_code=404, detail="이벤트를 찾을 수 없습니다.")
    _save(new, user, settings)
