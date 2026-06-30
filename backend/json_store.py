"""JSON 파일 원자적 쓰기 + 경로별 락.

동시 요청(예: AI가 일정 생성 + UI가 설정 저장)에서의 lost-update와
쓰기 도중 크래시로 인한 파일 손상을 방지한다.
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def lock_for(path: Path) -> threading.Lock:
    key = str(path.resolve())
    with _locks_guard:
        lk = _locks.get(key)
        if lk is None:
            lk = threading.Lock()
            _locks[key] = lk
        return lk


def write_atomic(path: Path, data) -> None:
    """같은 디렉토리 임시파일에 쓴 뒤 os.replace로 원자 교체."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default
