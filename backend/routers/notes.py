"""노트 API: 마크다운 CRUD + 위키링크/백링크 + 그래프."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..auth import SessionUser, require_session
from ..config import Settings, get_settings
from ..notes_graph import backlinks_for, build_graph, parse_wikilinks
from ..security_paths import safe_join, to_rel
from ..storage import notes_root, scope_root
from ..trash import move_to_trash

router = APIRouter(prefix="/api/notes", tags=["notes"])


class NoteSummary(BaseModel):
    path: str
    title: str
    modified: float


class NoteDetail(BaseModel):
    path: str
    title: str
    content: str
    links: list[str]
    backlinks: list[str]


class SaveNote(BaseModel):
    path: str
    content: str


class GraphData(BaseModel):
    nodes: list[dict]
    links: list[dict]


class NoteTree(BaseModel):
    folders: list[str]  # 모든 폴더의 상대경로(POSIX)
    notes: list[NoteSummary]


class FolderRequest(BaseModel):
    path: str


class SearchHit(BaseModel):
    path: str
    title: str
    snippet: str


def _snippet(text: str, q: str, width: int = 60) -> str:
    low = text.lower()
    i = low.find(q.lower())
    if i < 0:
        return text[:width].replace("\n", " ").strip()
    start = max(0, i - width // 2)
    seg = text[start : start + width].replace("\n", " ").strip()
    return ("…" if start > 0 else "") + seg + ("…" if start + width < len(text) else "")


def _ensure_md(path: str) -> str:
    return path if path.endswith(".md") else f"{path}.md"


def _note_root(base: str, scope: str, user: SessionUser, settings: Settings) -> Path:
    """base='files' → 파일 저장소(scope_root)로 .md 편집, 그 외 → 노트 폴더(notes_root).

    이로써 노트 페이지에서 파일 페이지의 폴더(hdd)를 열어 마크다운을 보고 수정할 수 있다.
    """
    if base == "files":
        return scope_root(scope, user, settings)
    return notes_root(scope, user, settings)


def _trash_kind(base: str) -> str:
    return "file" if base == "files" else "note"


@router.get("/list", response_model=list[NoteSummary])
def list_notes(
    scope: str = Query("me"),
    base: str = Query("notes"),
    user: SessionUser = Depends(require_session),
    settings: Settings = Depends(get_settings),
):
    root = _note_root(base, scope, user, settings)
    out = []
    for p in sorted(root.rglob("*.md")):
        if p.is_file():
            out.append(
                NoteSummary(
                    path=to_rel(root, p), title=p.stem, modified=p.stat().st_mtime
                )
            )
    return out


@router.get("/tree", response_model=NoteTree)
def notes_tree(
    scope: str = Query("me"),
    base: str = Query("notes"),
    user: SessionUser = Depends(require_session),
    settings: Settings = Depends(get_settings),
):
    """폴더 목록 + 노트 목록. 프론트에서 중첩 트리로 구성."""
    root = _note_root(base, scope, user, settings)
    folders: list[str] = []
    notes: list[NoteSummary] = []
    for p in sorted(root.rglob("*")):
        if p.is_dir():
            folders.append(to_rel(root, p))
        elif p.is_file() and p.suffix == ".md":
            notes.append(
                NoteSummary(path=to_rel(root, p), title=p.stem, modified=p.stat().st_mtime)
            )
    return NoteTree(folders=folders, notes=notes)


@router.post("/folder")
def create_folder(
    req: FolderRequest,
    scope: str = Query("me"),
    base: str = Query("notes"),
    user: SessionUser = Depends(require_session),
    settings: Settings = Depends(get_settings),
):
    root = _note_root(base, scope, user, settings)
    target = safe_join(root, req.path)
    if target == root:
        raise HTTPException(status_code=400, detail="폴더 이름이 비어 있습니다.")
    if target.exists():
        raise HTTPException(status_code=409, detail="이미 존재합니다.")
    target.mkdir(parents=True)
    return {"ok": True, "path": to_rel(root, target)}


@router.delete("/folder")
def delete_folder(
    scope: str = Query("me"),
    base: str = Query("notes"),
    path: str = Query(...),
    user: SessionUser = Depends(require_session),
    settings: Settings = Depends(get_settings),
):
    """폴더를 하위 노트와 함께 휴지통으로 이동."""
    root = _note_root(base, scope, user, settings)
    target = safe_join(root, path)
    if target == root:
        raise HTTPException(status_code=400, detail="루트는 삭제할 수 없습니다.")
    if not target.exists() or not target.is_dir():
        raise HTTPException(status_code=404, detail="폴더를 찾을 수 없습니다.")
    move_to_trash(_trash_kind(base), scope, target, to_rel(root, target), user, settings)
    return {"ok": True}


@router.get("/get", response_model=NoteDetail)
def get_note(
    scope: str = Query("me"),
    base: str = Query("notes"),
    path: str = Query(...),
    user: SessionUser = Depends(require_session),
    settings: Settings = Depends(get_settings),
):
    root = _note_root(base, scope, user, settings)
    target = safe_join(root, _ensure_md(path))
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="노트를 찾을 수 없습니다.")
    content = target.read_text(encoding="utf-8", errors="replace")
    return NoteDetail(
        path=to_rel(root, target),
        title=target.stem,
        content=content,
        links=parse_wikilinks(content),
        backlinks=backlinks_for(root, target.stem),
    )


@router.put("/save", response_model=NoteSummary)
def save_note(
    req: SaveNote,
    scope: str = Query("me"),
    base: str = Query("notes"),
    user: SessionUser = Depends(require_session),
    settings: Settings = Depends(get_settings),
):
    root = _note_root(base, scope, user, settings)
    target = safe_join(root, _ensure_md(req.path))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(req.content, encoding="utf-8")
    return NoteSummary(
        path=to_rel(root, target), title=target.stem, modified=target.stat().st_mtime
    )


@router.delete("/delete")
def delete_note(
    scope: str = Query("me"),
    base: str = Query("notes"),
    path: str = Query(...),
    user: SessionUser = Depends(require_session),
    settings: Settings = Depends(get_settings),
):
    root = _note_root(base, scope, user, settings)
    target = safe_join(root, _ensure_md(path))
    if not target.exists():
        raise HTTPException(status_code=404, detail="노트를 찾을 수 없습니다.")
    # 즉시 삭제 대신 휴지통으로 이동
    move_to_trash(_trash_kind(base), scope, target, to_rel(root, target), user, settings)
    return {"ok": True}


@router.get("/search", response_model=list[SearchHit])
def search_notes(
    scope: str = Query("me"),
    base: str = Query("notes"),
    q: str = Query(..., min_length=1),
    user: SessionUser = Depends(require_session),
    settings: Settings = Depends(get_settings),
):
    """제목·내용 전문 검색. 매치 스니펫 포함."""
    root = _note_root(base, scope, user, settings)
    ql = q.lower()
    hits: list[SearchHit] = []
    for p in sorted(root.rglob("*.md")):
        if not p.is_file():
            continue
        title = p.stem
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if ql in title.lower() or ql in text.lower():
            hits.append(
                SearchHit(path=to_rel(root, p), title=title, snippet=_snippet(text, q))
            )
        if len(hits) >= 50:
            break
    return hits


@router.get("/graph", response_model=GraphData)
def graph(
    scope: str = Query("me"),
    base: str = Query("notes"),
    folder: str = Query(""),
    mode: str = Query("links"),
    user: SessionUser = Depends(require_session),
    settings: Settings = Depends(get_settings),
):
    root = _note_root(base, scope, user, settings)
    return build_graph(root, folder=folder or None, mode=mode)
