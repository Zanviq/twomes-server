"""Hermes 교차 세션 메모리 — aidoc 문서 재사용(mem_type/feature_key).

메모리 = documents 중 mem_type IS NOT NULL. scope는 project 컬럼으로 표현:
global은 sentinel '_global', 프로젝트는 실제 이름. 일반 문서 도구는 mem_type IS NULL만
다루므로 서로 오염되지 않는다. 임베딩/버전/의미검색은 aidoc 그대로 재사용.
"""
from __future__ import annotations

from . import audit, db, embeddings, ids, paths, service, store
from .errors import BadRequest, NotFound

GLOBAL = "_global"  # global 메모리의 project sentinel(일반 문서는 절대 안 씀)
MEM_TYPES = ("preference", "mistake", "decision", "feature")


def _scope_project(scope: str) -> str:
    return GLOBAL if scope == "global" else scope


def _scope_dir(scope: str) -> str:
    return "memory/global" if scope == "global" else f"memory/projects/{scope}"


def _validate_scope(settings, scope: str) -> None:
    if scope == "global":
        return
    from . import projects as _projects
    if not _projects.is_registered(settings, scope):
        raise BadRequest(f"등록되지 않은 프로젝트: {scope}")


def _last_change(conn, doc_id: str):
    r = conn.execute(
        "SELECT change_summary FROM document_versions WHERE doc_id=? ORDER BY version DESC LIMIT 1",
        (doc_id,),
    ).fetchone()
    return r["change_summary"] if r else None


def _last_changes(conn, doc_ids) -> dict[str, str]:
    """여러 문서의 최신 버전 change_summary를 한 쿼리로(문서당 별도 쿼리 N+1 제거)."""
    doc_ids = list(doc_ids)
    if not doc_ids:
        return {}
    ph = ",".join("?" * len(doc_ids))
    rows = conn.execute(
        f"SELECT dv.doc_id AS doc_id, dv.change_summary AS cs FROM document_versions dv "
        f"JOIN (SELECT doc_id, MAX(version) mv FROM document_versions WHERE doc_id IN ({ph}) "
        f"GROUP BY doc_id) m ON dv.doc_id=m.doc_id AND dv.version=m.mv",
        doc_ids,
    ).fetchall()
    return {r["doc_id"]: r["cs"] for r in rows}


def _hit(settings, row, score: float, full: bool, last_change) -> dict:
    proj = row["project"]
    content = store.read(settings, row["storage_path"])
    h = {
        "id": row["id"], "feature_key": row["feature_key"], "mem_type": row["mem_type"],
        "scope": "global" if proj == GLOBAL else proj, "title": row["title"],
        "score": round(float(score), 4), "updated_at": row["updated_at"],
        "version": row["version"], "last_change": last_change,
    }
    if full:
        h["content"] = content
    else:
        h["summary"] = content.strip().replace("\n", " ")[:240]
    return h


def _create_memory(settings, actor, scope, mem_type, title, content, feature_key) -> str:
    dir_rel = _scope_dir(scope)
    paths.resolve_rel(settings, dir_rel).mkdir(parents=True, exist_ok=True)
    slug = ids.safe_slug(title or feature_key or "memory")
    fname = ids.unique_filename(dir_rel, slug, paths.list_existing_names(settings, dir_rel))
    storage_path = f"{dir_rel}/{fname}"
    doc_id = ids.new_document_id()
    now = service._now()
    proj = _scope_project(scope)
    store.write_new(settings, storage_path, content)
    conn = db.connect(settings)
    try:
        conn.execute(
            "INSERT INTO documents(id,title,project,category,tags,status,storage_path,version,"
            "content_hash,created_by,updated_by,created_at,updated_at,mem_type,feature_key) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (doc_id, title, proj, None, "[]", "memory", storage_path, 1, store.sha256(content),
             actor.name, actor.name, now, now, mem_type, feature_key),
        )
        service._index_fts(conn, doc_id, title, content, [], proj, mem_type)
        audit.log(conn, actor.name, "remember_create", doc_id=doc_id, project=proj, to_version=1)
        conn.commit()
    finally:
        conn.close()
    embeddings.index_document(settings, doc_id, title, content, store.sha256(content))
    return doc_id


def remember(settings, actor, scope, mem_type, title, content, feature_key=None, change_note="") -> dict:
    """메모리 기록. feature_key로 기존 메모리 발견 시 같은 문서를 새 버전으로 갱신(진화 로그)."""
    _validate_scope(settings, scope)
    if mem_type not in MEM_TYPES:
        raise BadRequest(f"mem_type은 {list(MEM_TYPES)} 중 하나여야 합니다.")
    if not (title and title.strip()):
        raise BadRequest("title이 필요합니다.")
    if len((content or "").encode("utf-8")) > settings.aidoc_max_bytes:
        raise BadRequest("본문이 너무 큽니다.")
    proj = _scope_project(scope)
    existing = None
    if feature_key:
        conn = db.connect(settings)
        try:
            existing = conn.execute(
                "SELECT id FROM documents WHERE mem_type IS NOT NULL AND project=? "
                "AND feature_key=? AND trashed=0",
                (proj, feature_key),
            ).fetchone()
        finally:
            conn.close()
    if existing:
        # 같은 기능 = 같은 문서: 현재본 전체 교체 + change_note를 진화 로그(버전이력)로
        service._apply_new_content(settings, actor, existing["id"], title,
                                   lambda _old: content, change_note or "update")
        doc_id = existing["id"]
    else:
        doc_id = _create_memory(settings, actor, scope, mem_type, title, content, feature_key)
    return get_memory(settings, doc_id, full=True)


def get_memory(settings, doc_id: str, full: bool = True) -> dict:
    conn = db.connect(settings)
    try:
        row = conn.execute(
            "SELECT * FROM documents WHERE id=? AND mem_type IS NOT NULL", (doc_id,)
        ).fetchone()
        if not row:
            raise NotFound("메모리를 찾을 수 없습니다.")
        return _hit(settings, row, 1.0, full, _last_change(conn, doc_id))
    finally:
        conn.close()


def _fts_recall(settings, query, scopes, limit) -> list[tuple[float, str]]:
    conn = db.connect(settings)
    try:
        ph = ",".join("?" * len(scopes))
        if db.has_fts5(conn):
            fq = service._fts_query(query)
            if fq:
                cur = conn.execute(
                    f"SELECT d.id AS id FROM documents_fts f JOIN documents d ON d.id=f.doc_id "
                    f"WHERE documents_fts MATCH ? AND d.trashed=0 AND d.mem_type IS NOT NULL "
                    f"AND d.project IN ({ph}) LIMIT ?",
                    [fq, *scopes, int(limit)],
                )
                return [(0.0, r["id"]) for r in cur.fetchall()]
        ql = f"%{(query or '').lower()}%"
        cur = conn.execute(
            f"SELECT id FROM documents WHERE trashed=0 AND mem_type IS NOT NULL "
            f"AND project IN ({ph}) AND lower(title) LIKE ? LIMIT ?",
            [*scopes, ql, int(limit)],
        )
        return [(0.0, r["id"]) for r in cur.fetchall()]
    finally:
        conn.close()


def recall(settings, query, project=None, limit=8, full=False) -> list[dict]:
    """메모리(global + 지정 project) 의미검색. full=True면 본문 전체, 아니면 요약."""
    if not (query and query.strip()):
        return []
    scopes = [GLOBAL] + ([project] if project else [])
    qvec = embeddings.embed_text(settings, query, task_type="RETRIEVAL_QUERY")
    if qvec:
        qn = embeddings.normalize(qvec)
        scored: list[tuple[float, str]] = []
        for sc in scopes:
            for doc_id, vec in embeddings.load_vectors(settings, project=sc, memory=True):
                scored.append((embeddings.dot(qn, vec), doc_id))
        scored.sort(reverse=True)
        top = scored[: max(1, int(limit))]
    else:
        top = _fts_recall(settings, query, scopes, limit)
    if not top:
        return []
    ids = [doc_id for _, doc_id in top]
    conn = db.connect(settings)
    try:
        ph = ",".join("?" * len(ids))
        rows = conn.execute(
            f"SELECT * FROM documents WHERE id IN ({ph}) AND mem_type IS NOT NULL AND trashed=0",
            ids,
        ).fetchall()
        changes = _last_changes(conn, ids)  # 배치로 최신 change_summary 조회
    finally:
        conn.close()
    by_id = {r["id"]: r for r in rows}
    out = []
    for score, doc_id in top:  # 점수 순서 유지
        row = by_id.get(doc_id)
        if row:
            out.append(_hit(settings, row, score, full, changes.get(doc_id)))
    return out


def list_memories(settings, scope=None, mem_type=None) -> list[dict]:
    where = ["mem_type IS NOT NULL", "trashed=0"]; vals: list = []
    if scope:
        where.append("project=?"); vals.append(_scope_project(scope))
    if mem_type:
        where.append("mem_type=?"); vals.append(mem_type)
    conn = db.connect(settings)
    try:
        rows = conn.execute(
            "SELECT id,title,project,mem_type,feature_key,updated_at,version FROM documents "
            f"WHERE {' AND '.join(where)} ORDER BY updated_at DESC",
            vals,
        ).fetchall()
    finally:
        conn.close()
    return [
        {"id": r["id"], "title": r["title"],
         "scope": "global" if r["project"] == GLOBAL else r["project"],
         "mem_type": r["mem_type"], "feature_key": r["feature_key"],
         "updated_at": r["updated_at"], "version": r["version"]}
        for r in rows
    ]
