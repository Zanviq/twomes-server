# Hermes MCP — 다른 프로젝트 AI 세션용 온보딩 프롬프트

> 이 문서는 **다른 프로젝트(orchestra-room, conversation-tree-ai, nodi 등)에서 작업하는 Claude/Codex 세션**에게 그대로 제공하는 지침이다.
> 프로젝트의 `CLAUDE.md`/`AGENTS.md`에 붙여넣거나 세션 시작 시 컨텍스트로 넣으면 된다.
> (연결 방법은 `docs/aidoc-mcp-connection.md` 참고 — `claude mcp add --transport http hermes https://mcp.zanviq.dev/mcp --header "Authorization: Bearer <토큰>"`)

---

## 너에게 주어진 것: Hermes MCP

너는 **Hermes**라는 MCP 서버에 연결되어 있다. 이것은 자가 호스팅 홈서버(라즈베리파이)가 제공하는 두 가지다:

1. **문서 저장소** — 프로젝트 문서를 홈서버에 저장/검색/편집. 버전·이력·의미검색 지원.
2. **교차 세션 메모리** — 여러 프로젝트·여러 세션이 공유하는 지속 기억. "사용자가 실제로 원하는 것", "과거에 어떻게 했는지", "무슨 실수를 했는지"를 기록하고 회상한다.

**핵심 목적:** 사용자가 매 프로젝트마다 같은 지시를 반복하지 않게 하는 것. 너는 작업 전에 기억을 확인하고, 사용자가 네 결과물을 고치면 그것을 기록해 다음 세션이 반복하지 않게 한다.

---

## ⭐ 반드시 지킬 메모리 프로토콜

### 1) 작업을 시작하기 전에 `recall` 하라
새 기능·수정·결정에 착수하기 **전에**, 관련 주제로 회상해서 과거 결정·사용자 성향·실수를 확인한다.

```
recall(query="캘린더 색상 규칙", project="<너의 프로젝트명>")
```
- `global`(사용자 전역 성향) + 지정한 `project` 메모리를 의미(임베딩) 기반으로 검색한다. 키워드가 안 겹쳐도 뜻으로 찾는다.
- 기본은 **요약**만 온다. 정확한 이전 내용을 봐야 하면 `full=true`.
- 회상 결과가 있으면 **그 결정/성향을 따르고**, 다시 묻지 마라.

### 2) 사용자가 네 결과물을 정정하면 `remember` 하라
AI가 만든 것을 사용자가 바꾸면(= 진짜 사용자 의도가 드러난 순간), 반드시 기록한다.

```
remember(
  scope="<프로젝트명 또는 global>",
  type="preference | mistake | decision | feature",
  title="캘린더 색상 규칙",
  content="<현재 최종 상태 전체>",
  feature_key="calendar-color-rules",
  change_note="AI가 파란색을 기본으로 했는데, 사용자가 '동아리는 보라색'을 요청 → 이름 기반 색상 규칙으로 변경"
)
```

### 3) "같은 기능 = 같은 문서" (가장 중요)
같은 기능이 여러 번 수정되면 **매번 새 메모리를 만들지 말고, 같은 `feature_key`로 같은 문서를 갱신**한다.
- `feature_key`는 안정적인 kebab 슬러그(예: `calendar-color-rules`, `note-graph-design`, `ui-accent-color`). 같은 기능엔 항상 같은 키.
- `remember`가 그 키의 기존 메모리를 찾아 **새 버전으로 갱신**한다. `content`엔 항상 **현재 최종 상태 전체**를 넣고, `change_note`엔 이번에 무엇이 왜 바뀌었는지(AI안 → 사용자 의도)를 한 줄.
- 결과: 한 문서가 그 기능의 전체 진화를 담고, **최신 버전 = 최종 진실**. 다음 세션은 recall로 그 최종본만 보면 된다.

### 언제 무엇을 기록하나
| type | 무엇 | scope |
|---|---|---|
| `preference` | 사용자의 고정 취향/방식(예: "퍼스널 퍼플", "한국어 UI", "자동 알림 금지") | 보통 `global` |
| `mistake` | 저지른 실수 + 올바른 방법(예: "낙관적 잠금 없이 append하면 손실") | `global` 또는 프로젝트 |
| `decision` | 왜 이 방식을 골랐는지(대안 대비) | 프로젝트 |
| `feature` | 기능의 진화 이력(feature_key 필수) | 프로젝트 |

- **scope=`global`**: 모든 프로젝트에 적용되는 사용자 전역 지식(성향·일반 교훈). 어느 프로젝트의 AI든 읽고 쓴다.
- **scope=`<프로젝트명>`**: 그 프로젝트에만 해당하는 결정·기능·실수.

---

## 도구 목록

### 메모리 (Hermes)
- `recall(query, project?, limit?, full?)` — 의미검색 회상. global + project. `full=true`면 본문 전체.
- `remember(scope, type, title, content, feature_key?, change_note?)` — 기록/업서트.
- `list_memories(scope?, type?)` — 메모리 목록(간결 메타).

### 문서 (홈서버 저장소)
- `list_projects()` — 접근 가능한 프로젝트.
- `list_documents(project?)` / `search_documents(q)` — 목록 / 전문(FTS) 검색.
- `semantic_search(query, project?, limit?)` — 의미(임베딩) 검색. 관련 문서 탐색.
- `get_document(document_id)` — 상세(본문).
- `create_document(title, content?, project?, folder?, tags?, ...)` — 생성. `folder`로 하위 폴더 지정(자동 생성).
- `update_document(document_id, expected_version, content?, title?, change_summary?)` — 수정(낙관적 잠금; 먼저 get으로 최신 version 확인). 409면 최신 재조회.
- `append_document(document_id, content, change_summary?)` — 끝에 덧붙이기.
- `move_document(document_id, target_project?, target_folder?)` — 이동.
- `trash_document` / `restore_document(document_id, version?)` — 휴지통 / 복원(휴지통 또는 특정 버전).
- `get_document_history(document_id)` — 버전 이력.
- `export_folder(project?, folder?, recursive?)` — 웹 폴더의 **내용물**(안의 파일들)을 relative_path+content로 반환 → 먼저 로컬 대상 폴더를 정한 뒤 `<로컬>/<relative_path>`로 저장.
- `reindex()` — 임베딩 누락/변경분 재색인(옛 문서 검색·그래프 포함).

---

## 이 서버(SERVER/홈서버)는 무엇인가
- 라즈베리파이5 자가 호스팅 홈서버. FastAPI 백엔드 + React 프런트, Docker Compose, Cloudflare 터널(`server.zanviq.dev`, MCP는 `mcp.zanviq.dev`).
- 웹 UI: 파일 관리, 노트(그래프뷰·[[링크]]), 캘린더(Google 연동 + AI 비서), AI 채팅, 로컬 폴더 동기화, 웹 터미널(admin).
- **AI 문서 시스템(aidoc)** = 지금 네가 쓰는 이 MCP의 백엔드. 문서는 `/mnt/hdd/server/AI_documents`에 저장, 임베딩은 Gemini(gemini-embedding-001, 768차원).
- 웹에서도 노트 페이지 → "AI 문서" 소스로 같은 문서를 열람·편집하고, 그래프 페이지 → "AI 문서"로 임베딩 유사도 지식 그래프를 본다.

---

## 빠른 시작 체크리스트 (매 작업)
1. 착수 전 `recall("<이 작업 주제>", project="<프로젝트>")` → 과거 결정·사용자 성향 확인 후 반영.
2. 필요하면 `semantic_search`로 관련 기존 문서 탐색.
3. 작업 수행. 산출물/설계는 `create_document`/`update_document`로 홈서버에 남긴다(프로젝트·폴더 정리).
4. 사용자가 정정하면 즉시 `remember(...)` — 같은 기능이면 같은 `feature_key`로 갱신, `change_note`에 "AI안 → 사용자 의도".
5. 되돌릴 수 없는 작업(삭제 등)은 확인 후. 영구삭제는 없음(휴지통만).

> 한 줄 요약: **작업 전 recall, 정정 후 remember, 같은 기능은 같은 feature_key.**
