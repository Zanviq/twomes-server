"""로컬↔서버 문서 3-way 동기화 '계획' 산출(순수 로직, 부작용 없음).

로컬은 `.hermes-sync.json` 매니페스트에 파일별 baseline{id, synced_version,
synced_hash}을 둔다. 이 모듈은 (로컬 현재해시 L, baseline B, 서버 현재해시 S)를
비교해 각 경로를 pull/push/삭제/충돌로 분류만 한다. 실제 변경(파일 쓰기·서버
update/create/trash)은 호출자(AI)가 기존 도구로 수행한다.

분류(요약):
  B 없음(미동기): 로컬만→push_create / 서버만→pull_create / 둘 다 같음→noop / 다름→conflict
  L=B=S: noop
  로컬만 변경(S=B): L 있음→push / L 없음(로컬삭제)→delete_server
  서버만 변경(L=B): S 있음→pull / S 없음(서버삭제)→delete_local
  양쪽 변경(L≠S): conflict — mode('local'|'server'|'ai')로만 해소

mode는 '진짜 충돌'(양쪽이 서로 다르게 변경, 삭제 vs 수정 포함)에만 적용된다.
한쪽만 바뀐 변경과 신규 파일은 방향이 자명하므로 mode와 무관하게 반영한다.
"""
from __future__ import annotations

import hashlib

VALID_MODES = ("local", "server", "ai")


def content_hash(text: str) -> str:
    """개행을 LF로 정규화한 UTF-8 본문의 sha256(hex).

    서버·로컬(AI)이 동일하게 계산해야 baseline 비교가 성립한다. 정규화는 CRLF/CR
    → LF만 수행(플랫폼 개행 차이 흡수). 그 외 공백은 건드리지 않는다.
    """
    norm = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def _kind(local_hash, server_hash) -> str:
    if local_hash is None:
        return "local_deleted_server_edited"
    if server_hash is None:
        return "local_edited_server_deleted"
    return "both_edited"


def plan(entries, server_docs, mode: str = "ai") -> dict:
    """3-way 비교로 동기화 계획을 만든다.

    entries: [{path, local_hash|None, synced_version|None, synced_hash|None}]
        local_hash None → 로컬 삭제(또는 없음). synced_hash None → 매니페스트에
        없던 신규 파일(baseline 없음).
    server_docs: {rel_path: {id, version, hash, content}} — 스코프 내 서버 현재 상태.
    mode: 'local'|'server'|'ai'. 진짜 충돌에만 적용.

    반환 키: pull, pull_create, push, push_create, delete_local, delete_server,
    conflict, noop. (각 항목은 호출자가 그대로 실행할 수 있는 dict)
    """
    if mode not in VALID_MODES:
        raise ValueError(f"알 수 없는 mode: {mode}")

    out: dict[str, list] = {
        "pull": [], "pull_create": [], "push": [], "push_create": [],
        "delete_local": [], "delete_server": [], "conflict": [], "noop": [],
    }

    local: dict[str, dict] = {}
    for e in entries or []:
        local[e["path"]] = {
            "L": e.get("local_hash"),
            "B": e.get("synced_hash"),
            "base_version": e.get("synced_version"),
        }

    for path in sorted(set(local) | set(server_docs)):
        le = local.get(path)
        L = le["L"] if le else None                 # 로컬 현재 해시
        B = le["B"] if le else None                 # baseline 해시
        base_version = le["base_version"] if le else None
        sd = server_docs.get(path)
        S = sd["hash"] if sd else None              # 서버 현재 해시
        sid = sd["id"] if sd else None
        sver = sd["version"] if sd else None

        # ── baseline 없음(이전에 동기화된 적 없음) ──
        if B is None:
            if L is not None and S is None:
                out["push_create"].append({"path": path})
            elif L is None and S is not None:
                out["pull_create"].append(_pull_item(path, sid, sver, sd))
            elif L is not None and S is not None:
                if L == S:
                    out["noop"].append({"path": path, "id": sid, "version": sver})
                else:
                    out["conflict"].append(_conflict_item(path, sid, sver, sd, None, "both_new"))
            # L None and S None → 양쪽 다 없음: 무시
            continue

        # ── baseline 있음 ──
        local_changed = L != B
        server_changed = S != B

        if not local_changed and not server_changed:
            out["noop"].append({"path": path, "id": sid, "version": sver})
        elif local_changed and not server_changed:
            if L is None:  # 로컬 삭제 미러링 → 서버 trash
                out["delete_server"].append({"path": path, "id": sid, "expected_version": sver})
            else:
                out["push"].append({"path": path, "id": sid, "expected_version": sver})
        elif server_changed and not local_changed:
            if S is None:  # 서버 삭제 미러링 → 로컬 rm
                out["delete_local"].append({"path": path, "id": sid})
            else:
                out["pull"].append(_pull_item(path, sid, sver, sd))
        else:  # 양쪽 변경
            if L == S:
                out["noop"].append({"path": path, "id": sid, "version": sver})
            else:
                _resolve(out, mode, path, L, S, sid, sver, sd, base_version)

    return out


def _resolve(out, mode, path, L, S, sid, sver, sd, base_version) -> None:
    """진짜 충돌 해소. local/server는 자동 방향 결정, ai는 conflict로 보고."""
    if mode == "local":
        if L is not None:  # 로컬 우선 → 서버 덮어쓰기
            if S is not None:
                out["push"].append({"path": path, "id": sid, "expected_version": sver})
            else:  # 서버 문서가 삭제됨 → 재생성
                out["push_create"].append({"path": path})
        elif sid is not None:  # 로컬 삭제 우선 → 서버 trash
            out["delete_server"].append({"path": path, "id": sid, "expected_version": sver})
    elif mode == "server":
        if S is not None:  # 서버 우선 → 로컬 덮어쓰기
            out["pull"].append(_pull_item(path, sid, sver, sd))
        else:  # 서버 삭제 우선 → 로컬 rm
            out["delete_local"].append({"path": path, "id": sid})
    else:  # ai — 판단을 넘긴다
        out["conflict"].append(_conflict_item(path, sid, sver, sd, base_version, _kind(L, S)))


def _pull_item(path, sid, sver, sd) -> dict:
    return {"path": path, "id": sid, "version": sver, "content": sd["content"] if sd else None}


def _conflict_item(path, sid, sver, sd, base_version, kind) -> dict:
    return {
        "path": path, "id": sid, "kind": kind,
        "base_version": base_version, "server_version": sver,
        "server_content": sd["content"] if sd else None,
    }
