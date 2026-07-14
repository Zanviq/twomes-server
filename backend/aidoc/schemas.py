"""AI 문서 API 스키마."""
from __future__ import annotations

from pydantic import BaseModel, Field


class CreateDoc(BaseModel):
    title: str
    content: str = ""
    project: str | None = None
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    status: str = "draft"
    folder: str | None = None  # 프로젝트/인박스 하위 폴더(선택). 없으면 자동 생성.
    duplicate_check_query: str | None = None


class CreateFolder(BaseModel):
    project: str | None = None  # None → inbox 하위
    path: str  # 하위 폴더 경로(예: "설계/초안")


class ProjectBody(BaseModel):
    name: str


class RememberBody(BaseModel):
    scope: str  # 'global' 또는 프로젝트명
    type: str   # preference|mistake|decision|feature
    title: str
    content: str = ""
    feature_key: str | None = None
    change_note: str = ""


class UpdateDoc(BaseModel):
    expected_version: int
    title: str | None = None
    content: str | None = None
    change_summary: str = ""


class AppendDoc(BaseModel):
    content: str
    change_summary: str = ""


class MoveDoc(BaseModel):
    target_project: str | None = None  # None → inbox
    target_folder: str | None = None   # knowledge/... 등 (등록 폴더만)


class RestoreDoc(BaseModel):
    version: int | None = None  # None → 휴지통 복원, 값 → 해당 버전으로 복원


class SyncEntry(BaseModel):
    path: str  # 스코프 기준 상대경로(= 서버 relative_path)
    local_hash: str | None = None       # 로컬 현재 본문 해시(LF 정규화 sha256). None=로컬 삭제
    synced_version: int | None = None   # 매니페스트 baseline 버전(신규=None)
    synced_hash: str | None = None       # 매니페스트 baseline 해시(신규=None)


class SyncPlanBody(BaseModel):
    project: str | None = None
    folder: str | None = None
    mode: str = "ai"  # local|server|ai (진짜 충돌에만 적용)
    entries: list[SyncEntry] = Field(default_factory=list)


class DocMeta(BaseModel):
    id: str
    title: str
    project: str | None
    category: str | None
    tags: list[str]
    status: str
    version: int
    created_by: str | None
    updated_by: str | None
    created_at: str
    updated_at: str
    trashed: bool


class DocDetail(DocMeta):
    content: str


class SearchHit(DocMeta):
    snippet: str
