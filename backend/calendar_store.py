"""내부 캘린더 저장소 — 사용자별 events.json.

이벤트 모델(CalenMate 호환):
  {id, title, description, start(ISO), end(ISO), allDay(bool), color}
"""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import HTTPException

from . import json_store
from .auth import SessionUser
from .config import Settings


def _events_path(user: SessionUser, settings: Settings) -> Path:
    base = settings.user_root(user.username) / "calendar"
    base.mkdir(parents=True, exist_ok=True)
    return base / "events.json"


def _load(user: SessionUser, settings: Settings) -> list[dict]:
    data = json_store.read_json(_events_path(user, settings), [])
    return data if isinstance(data, list) else []


def _save(events: list[dict], user: SessionUser, settings: Settings) -> None:
    json_store.write_atomic(_events_path(user, settings), events)


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
    with json_store.lock_for(_events_path(user, settings)):
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
    with json_store.lock_for(_events_path(user, settings)):
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
    with json_store.lock_for(_events_path(user, settings)):
        events = _load(user, settings)
        new = [e for e in events if e["id"] != eid]
        if len(new) == len(events):
            raise HTTPException(status_code=404, detail="이벤트를 찾을 수 없습니다.")
        _save(new, user, settings)
