# AI 문서 임베딩·벡터검색·그래프·폴더 설계 (SERVER)

**작성일:** 2026-07-13
**대상:** aidoc 문서에 Gemini 임베딩 기반 의미 검색·의미 그래프뷰·폴더 정리를 추가

## 확정 결정 (사용자 승인)
- **그래프 엣지:** 임베딩 코사인 유사도 + 본문 `[[제목]]` 링크 **병행**
- **임베딩 시점:** 문서 생성/수정 시 **자동**(best-effort — 실패해도 문서 저장 성공) + `reindex` 보정
- **폴더:** 프로젝트/지식 하위에 **자유 폴더** 생성·정리
- **임베딩:** Gemini `gemini-embedding-001`(google-genai, 기존 의존성) — GEMINI_API_KEY 재사용
- **벡터 저장/검색:** SQLite BLOB(float32, 정규화) + 순수 파이썬 코사인(소규모라 충분, 새 의존성 없음)
- **검색 범위 선택:** MCP 도구 `project` 인자(지정=그 프로젝트, 미지정=권한 내 전체)

## 아키텍처
```
Gemini embed_content ── embeddings.py ─┐
aidoc create/update ─(자동 best-effort)┴─ document_embeddings(doc_id,model,dim,vector,hash)
                                        │
semantic_search(query,project?) ─코사인─┼→ MCP 도구 semantic_search + REST
aidoc graph(project?) ─유사도+[[링크]]──┴→ /api/aidoc/graph → 그래프 페이지(소스 셀렉터)
폴더: create_folder + create/move의 subfolder ── AidocWorkspace 트리
```
- 임베딩(1)이 벡터검색(2)·그래프 엣지(3)를 공유. 권한/격리는 기존 `authz`(문서 실제 project 기준) 그대로.

## ① 임베딩 인프라
- **테이블** `document_embeddings(doc_id TEXT PK, model TEXT, dim INT, vector BLOB, content_hash TEXT, updated_at TEXT)` (db.py init에 추가, 멱등).
- **`backend/aidoc/embeddings.py`**:
  - `embed_text(settings, text) -> list[float] | None` — Gemini 호출. 키 없음/SDK 없음/오류 → None(로깅). 본문은 `AIDOC_EMBED_MAX_CHARS`로 자름.
  - `pack(vec)->bytes` / `unpack(bytes)->list[float]` (array 'f' float32).
  - `normalize(vec)->list[float]`, `dot(a,b)->float` (정규화 벡터 코사인=내적).
  - `index_document(settings, doc_id, text, model_hash_content) ` — embed + 정규화 + upsert `document_embeddings`. best-effort(예외 삼킴).
  - `load_vectors(settings, *, project=None, include_trashed=False) -> list[(doc_id, vec)]` — documents JOIN embeddings.
  - `reindex(settings) -> dict` — content_hash 불일치/누락 문서 일괄 임베딩. 반환 {indexed, skipped, failed}.
- **service 통합**: `create`, `_apply_new_content` 커밋 **후** `embeddings.index_document(...)` best-effort 호출(별도 커넥션 — 임베딩 실패가 문서 저장 롤백 안 함).
- **설정(.env)**: `AIDOC_EMBED_MODEL=gemini-embedding-001`, `AIDOC_EMBED_DIM=768`, `AIDOC_EMBED_MAX_CHARS=8000`, `AIDOC_GRAPH_EDGE_THRESHOLD=0.75`, `AIDOC_GRAPH_MAX_EDGES=4`.

## ② 벡터 검색
- **service** `semantic_search(settings, query, *, project=None, limit=10) -> list[dict]`:
  - `embed_text(query)`; None이면 FTS `search()`로 폴백.
  - `load_vectors(project=...)` → 코사인 정렬 → 상위 limit. 각 항목 DocMeta + `score` + `snippet`.
- **MCP 도구** `semantic_search`(12번째): params `query`(필수), `project`(선택 범위), `limit`(선택). authz: `documents:read`, project 지정 시 `need_resource`, 결과 `filter_allowed`.
- **REST**: `/api/aidoc/documents/semantic-search`(세션) + `/mcp/api/documents/semantic-search`(토큰). **`/documents/{doc_id}`보다 먼저 선언**.

## ③ 그래프뷰
- **backend** `GET /api/aidoc/graph?project=&threshold=&max_edges=` (세션):
  - 노드: 문서(id,title,project,tags,version). 프로젝트 필터 시 그 프로젝트만.
  - 엣지: (a) 임베딩 코사인 상위 K(노드당 `max_edges`, `threshold` 이상, 무방향 중복 제거) `kind:"similar"`; (b) 본문 `[[제목]]`을 제목 매칭으로 해석한 `kind:"link"`.
  - 반환 `{nodes:[...], links:[{source,target,weight,kind}]}`.
- **frontend** 그래프 페이지: 소스 셀렉터 **공통 노트 / 내 노트 / AI 문서**. AI 문서 선택 시 `/api/aidoc/graph` 호출, 기존 react-force-graph-2d + Nodi 노드 디자인 재사용. (선택) 프로젝트 필터 드롭다운.

## ④ AI 문서 폴더
- **service**: `create_folder(settings, project, rel)` → `projects/{project}/{rel}` mkdir(안전경로). `CreateDoc.folder`(선택) → storage_path에 하위폴더 반영. `move`의 target_folder를 프로젝트 하위 임의 폴더까지 확장.
- **frontend** AidocWorkspace: "새 폴더" 액션 + 트리를 storage_path 기준 폴더 그룹으로 표시(노트 페이지 트리와 유사). 문서를 폴더로 이동.

## 오류 처리·보안
- 임베딩·벡터검색·그래프는 **키 없으면 자동 비활성**(FTS·기존 기능 유지). 임베딩 실패는 문서 저장을 절대 막지 않음.
- 벡터검색/그래프도 토큰 scope·프로젝트 격리(IDOR 방어) 동일 적용. 경로는 `resolve_rel` 재검증.
- 벡터검색 `sqlite3.OperationalError` 등은 기존 `_mapped`가 503으로 매핑.

## 테스트
- **주입 가능한 가짜 임베더**(제목/본문→결정론적 벡터, 예: 문자 해시)로 네트워크·API키 없이 테스트: pack/unpack·normalize·dot, `index_document`·`load_vectors`, `semantic_search` 랭킹(가까운 문서 상위), 그래프 엣지(유사+링크), 폴더 생성/이동, MCP `semantic_search` 격리(타 프로젝트 미노출). 기존 `test_aidoc`/`test_smoke` 회귀.

## 제작 순서 (각 단계 = 계획→구현→검증→커밋)
- **A:** 임베딩 인프라 + 벡터검색 service + MCP 도구 + REST.
- **B:** 그래프 backend + 프런트 소스 셀렉터.
- **C:** AI 문서 폴더(service + AidocWorkspace).

## MVP 제외
sqlite-vec/ANN 인덱스(소규모라 브루트포스), 멀티모달 임베딩, 임베딩 캐시 워커(동기 best-effort), 그래프 실시간 갱신.
