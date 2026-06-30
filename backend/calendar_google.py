"""선택적 Google Calendar 어댑터.

env에 서비스계정 JSON 또는 OAuth refresh token이 있으면 활성화.
interactive 로그인 없이 동작. 미설정/오류 시 None을 반환해 내부 캘린더로 폴백.

내부 모델 {id,title,description,start,end,allDay,color} ↔ Google 이벤트 변환.
"""
from __future__ import annotations

import json
import logging

from .config import Settings

logger = logging.getLogger("twoems.gcal")

# Google colorId(1~11) 사용. 내부 color 필드를 그대로 colorId로 사용.


def _build_service(settings: Settings):
    """google-api-python-client 서비스 빌드. 실패 시 None."""
    try:
        from googleapiclient.discovery import build

        if settings.google_service_account_json:
            from google.oauth2 import service_account

            info = json.loads(_read_maybe_file(settings.google_service_account_json))
            creds = service_account.Credentials.from_service_account_info(
                info, scopes=["https://www.googleapis.com/auth/calendar"]
            )
        elif settings.google_client_id and settings.google_refresh_token:
            from google.oauth2.credentials import Credentials

            creds = Credentials(
                token=None,
                refresh_token=settings.google_refresh_token,
                client_id=settings.google_client_id,
                client_secret=settings.google_client_secret,
                token_uri="https://oauth2.googleapis.com/token",
                scopes=["https://www.googleapis.com/auth/calendar"],
            )
        else:
            return None
        return build("calendar", "v3", credentials=creds, cache_discovery=False)
    except Exception as e:  # pragma: no cover - 외부 의존
        logger.warning("Google Calendar 초기화 실패, 내부 캘린더로 폴백: %s", e)
        return None


def _read_maybe_file(value: str) -> str:
    """값이 파일 경로면 내용을, 아니면 그대로 반환(JSON 문자열 직접 주입 허용)."""
    import os

    if os.path.exists(value):
        with open(value, encoding="utf-8") as f:
            return f.read()
    return value


def _to_internal(g: dict) -> dict:
    start = g.get("start", {})
    end = g.get("end", {})
    all_day = "date" in start
    return {
        "id": g.get("id", ""),
        "title": g.get("summary", ""),
        "description": g.get("description", ""),
        "start": start.get("dateTime") or start.get("date") or "",
        "end": end.get("dateTime") or end.get("date") or "",
        "allDay": all_day,
        "color": g.get("colorId", "2"),
    }


def _to_google(p: dict) -> dict:
    all_day = bool(p.get("allDay"))
    body: dict = {
        "summary": p.get("title", ""),
        "description": p.get("description", ""),
        "colorId": str(p.get("color", "2")),
    }
    if all_day:
        body["start"] = {"date": p["start"][:10]}
        body["end"] = {"date": (p.get("end") or p["start"])[:10]}
    else:
        body["start"] = {"dateTime": p["start"], "timeZone": "Asia/Seoul"}
        body["end"] = {"dateTime": p.get("end") or p["start"], "timeZone": "Asia/Seoul"}
    return body


class GoogleCalendar:
    def __init__(self, service, calendar_id: str):
        self._svc = service
        self._cid = calendar_id

    def list(self, frm: str | None, to: str | None) -> list[dict]:
        params = {
            "calendarId": self._cid,
            "singleEvents": True,
            "orderBy": "startTime",
            "maxResults": 500,
        }
        if frm:
            params["timeMin"] = frm
        if to:
            params["timeMax"] = to
        items = self._svc.events().list(**params).execute().get("items", [])
        return [_to_internal(g) for g in items]

    def create(self, payload: dict) -> dict:
        g = (
            self._svc.events()
            .insert(calendarId=self._cid, body=_to_google(payload))
            .execute()
        )
        return _to_internal(g)

    def update(self, eid: str, payload: dict) -> dict:
        g = (
            self._svc.events()
            .patch(calendarId=self._cid, eventId=eid, body=_to_google(payload))
            .execute()
        )
        return _to_internal(g)

    def delete(self, eid: str) -> None:
        self._svc.events().delete(calendarId=self._cid, eventId=eid).execute()


def get_google_calendar(settings: Settings) -> GoogleCalendar | None:
    if not settings.google_enabled:
        return None
    svc = _build_service(settings)
    if svc is None:
        return None
    return GoogleCalendar(svc, settings.google_calendar_id)
