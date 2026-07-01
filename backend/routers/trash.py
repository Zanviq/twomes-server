"""휴지통 API: 목록·복원·영구삭제·비우기 (개인 스코프 전용)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..auth import SessionUser, require_session
from ..config import Settings, get_settings
from ..trash import empty, list_trash, purge, restore

router = APIRouter(prefix="/api/trash", tags=["trash"])


@router.get("/list")
def list_items(
    user: SessionUser = Depends(require_session),
    settings: Settings = Depends(get_settings),
):
    return list_trash(user, settings)


@router.post("/restore")
def restore_item(
    id: str = Query(...),
    user: SessionUser = Depends(require_session),
    settings: Settings = Depends(get_settings),
):
    return restore(id, user, settings)


@router.delete("/purge")
def purge_item(
    id: str = Query(...),
    user: SessionUser = Depends(require_session),
    settings: Settings = Depends(get_settings),
):
    return purge(id, user, settings)


@router.delete("/empty")
def empty_trash(
    user: SessionUser = Depends(require_session),
    settings: Settings = Depends(get_settings),
):
    return empty(user, settings)
