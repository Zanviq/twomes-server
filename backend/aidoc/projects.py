"""AI 문서 프로젝트 레지스트리 — 웹에서 추가/이름변경/삭제 가능한 동적 목록.

기존엔 AIDOC_PROJECTS(env)로 고정이었으나, DB 테이블 `projects`로 옮긴다.
env 값은 **최초 시드**로만 쓰인다(테이블이 비어 있을 때). 이후엔 DB가 권위.
"""
from __future__ import annotations

import os
import re
import shutil
from datetime import datetime, timezone

from ..config import Settings
from . import db
from .errors import BadRequest, NotFound
from .paths import resolve_rel

_NAME = re.compile(r"^[0-9a-z가-힣][0-9a-z가-힣._-]{0,63}$")


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _valid(name: str) -> str:
    n = (name or "").strip()
    if not _NAME.match(n) or ".." in n:
        raise BadRequest("프로젝트 이름은 영문 소문자/숫자/한글/._- 로 시작·구성해야 합니다.")
    return n


def _ensure_folders(settings: Settings, name: str) -> None:
    resolve_rel(settings, f"projects/{name}").mkdir(parents=True, exist_ok=True)
    resolve_rel(settings, f"memory/projects/{name}").mkdir(parents=True, exist_ok=True)


def ensure_seed(settings: Settings) -> None:
    """테이블이 비어 있으면 env(AIDOC_PROJECTS)로 최초 시드. 등록 프로젝트 폴더 보장."""
    conn = db.connect(settings)
    try:
        count = conn.execute("SELECT COUNT(*) AS c FROM projects").fetchone()["c"]
        if count == 0:
            for p in settings.aidoc_projects:
                conn.execute("INSERT OR IGNORE INTO projects(name,created_at) VALUES (?,?)", (p, _now()))
            conn.commit()
        names = [r["name"] for r in conn.execute("SELECT name FROM projects")]
    finally:
        conn.close()
    for n in names:
        _ensure_folders(settings, n)


def list_names(settings: Settings) -> list[str]:
    conn = db.connect(settings)
    try:
        return [r["name"] for r in conn.execute("SELECT name FROM projects ORDER BY name")]
    finally:
        conn.close()


def is_registered(settings: Settings, name: str) -> bool:
    conn = db.connect(settings)
    try:
        return conn.execute("SELECT 1 FROM projects WHERE name=?", (name,)).fetchone() is not None
    finally:
        conn.close()


def add(settings: Settings, name: str) -> dict:
    n = _valid(name)
    conn = db.connect(settings)
    try:
        if conn.execute("SELECT 1 FROM projects WHERE name=?", (n,)).fetchone():
            raise BadRequest("이미 존재하는 프로젝트입니다.")
        conn.execute("INSERT INTO projects(name,created_at) VALUES (?,?)", (n, _now()))
        conn.commit()
    finally:
        conn.close()
    _ensure_folders(settings, n)
    return {"name": n}


def rename(settings: Settings, old: str, new: str) -> dict:
    n = _valid(new)
    conn = db.connect(settings)
    try:
        if not conn.execute("SELECT 1 FROM projects WHERE name=?", (old,)).fetchone():
            raise NotFound("프로젝트를 찾을 수 없습니다.")
        if conn.execute("SELECT 1 FROM projects WHERE name=?", (n,)).fetchone():
            raise BadRequest("이미 존재하는 프로젝트입니다.")
    finally:
        conn.close()

    # 1) 폴더 이동(원자적 os.rename). 실패 시 되돌림.
    moved: list[tuple] = []
    try:
        for sub in ("projects", "memory/projects"):
            src = resolve_rel(settings, f"{sub}/{old}")
            dst = resolve_rel(settings, f"{sub}/{n}")
            if src.exists():
                os.rename(src, dst)
                moved.append((dst, src))
        # 2) DB 갱신(레지스트리 + 문서/메모리의 project·storage_path)
        conn = db.connect(settings)
        try:
            conn.execute("UPDATE projects SET name=? WHERE name=?", (n, old))
            rows = conn.execute(
                "SELECT id, storage_path FROM documents WHERE project=?", (old,)
            ).fetchall()
            for r in rows:
                sp = r["storage_path"]
                if sp.startswith(f"projects/{old}/"):
                    nsp = f"projects/{n}/" + sp[len(f"projects/{old}/"):]
                elif sp.startswith(f"memory/projects/{old}/"):
                    nsp = f"memory/projects/{n}/" + sp[len(f"memory/projects/{old}/"):]
                else:
                    nsp = sp
                conn.execute("UPDATE documents SET project=?, storage_path=? WHERE id=?", (n, nsp, r["id"]))
            conn.commit()
        finally:
            conn.close()
    except Exception:
        for dst, src in reversed(moved):  # 폴더 롤백
            try:
                os.rename(dst, src)
            except OSError:
                pass
        raise
    return {"name": n}


def delete(settings: Settings, name: str) -> dict:
    """프로젝트의 모든 문서를 휴지통으로 보내고 레지스트리에서 제거(영구삭제 아님)."""
    from . import service
    if not is_registered(settings, name):
        raise NotFound("프로젝트를 찾을 수 없습니다.")
    conn = db.connect(settings)
    try:
        ids = [r["id"] for r in conn.execute(
            "SELECT id FROM documents WHERE project=? AND trashed=0", (name,)
        ).fetchall()]
    finally:
        conn.close()
    for doc_id in ids:
        try:
            service.trash(settings, service.Actor("web"), doc_id)
        except Exception:  # noqa: BLE001
            pass
    conn = db.connect(settings)
    try:
        conn.execute("DELETE FROM projects WHERE name=?", (name,))
        conn.commit()
    finally:
        conn.close()
    # 비워진 폴더 정리(best-effort)
    for sub in ("projects", "memory/projects"):
        d = resolve_rel(settings, f"{sub}/{name}")
        try:
            if d.is_dir() and not any(d.iterdir()):
                shutil.rmtree(d)
        except OSError:
            pass
    return {"deleted": name, "trashed": len(ids)}
