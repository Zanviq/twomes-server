"""캘린더 API: 내부 저장소 또는 Google Calendar(설정 시)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from .. import calendar_store
from ..auth import SessionUser, require_session
from ..calendar_google import get_google_calendar
from ..config import Settings, get_settings

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


class EventInput(BaseModel):
    title: str
    description: str = ""
    start: str
    end: str | None = None
    allDay: bool = False
    color: str = "2"


class EventPatch(BaseModel):
    title: str | None = None
    description: str | None = None
    start: str | None = None
    end: str | None = None
    allDay: bool | None = None
    color: str | None = None


@router.get("/source")
def source(settings: Settings = Depends(get_settings)):
    """현재 캘린더 백엔드(google|internal)."""
    return {"source": "google" if get_google_calendar(settings) else "internal"}


@router.get("/events")
def list_events(
    frm: str | None = Query(None, alias="from"),
    to: str | None = Query(None),
    user: SessionUser = Depends(require_session),
    settings: Settings = Depends(get_settings),
):
    gc = get_google_calendar(settings)
    if gc:
        return gc.list(frm, to)
    return calendar_store.list_events(user, settings, frm, to)


@router.post("/events")
def create_event(
    body: EventInput,
    user: SessionUser = Depends(require_session),
    settings: Settings = Depends(get_settings),
):
    gc = get_google_calendar(settings)
    if gc:
        return gc.create(body.model_dump())
    return calendar_store.create_event(user, settings, body.model_dump())


@router.put("/events/{eid}")
def update_event(
    eid: str,
    body: EventPatch,
    user: SessionUser = Depends(require_session),
    settings: Settings = Depends(get_settings),
):
    payload = {k: v for k, v in body.model_dump().items() if v is not None}
    gc = get_google_calendar(settings)
    if gc:
        return gc.update(eid, payload)
    return calendar_store.update_event(user, settings, eid, payload)


@router.delete("/events/{eid}")
def delete_event(
    eid: str,
    user: SessionUser = Depends(require_session),
    settings: Settings = Depends(get_settings),
):
    gc = get_google_calendar(settings)
    if gc:
        gc.delete(eid)
    else:
        calendar_store.delete_event(user, settings, eid)
    return {"ok": True}
