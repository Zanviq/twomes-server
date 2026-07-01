"""기본 스킬 모음. 도메인별 모듈에서 집계.

모든 스킬은 SkillContext의 세션 사용자 스코프(common | 본인 me)에서만 동작한다.
"""
from __future__ import annotations

from .calendar import (
    CreateCalendarEvent,
    DeleteCalendarEvent,
    FindFreeSlots,
    ListCalendarEvents,
    UpdateCalendarEvent,
)
from .files import (
    AppendTextFile,
    CreateFolder,
    DeletePath,
    ListFiles,
    MovePath,
    ReadFile,
    SearchFiles,
    WriteTextFile,
)
from .notes import (
    AppendNote,
    DeleteNote,
    ListNotes,
    NoteBacklinks,
    ReadNote,
    RenameNote,
    SearchNotes,
    WriteNote,
)
from .system import GetSystemStatus
from .think import ThinkSkill

# 등록 순서 = LLM에 노출되는 카탈로그 순서
ALL_SKILLS = [
    ThinkSkill(),
    # 파일
    ListFiles(),
    ReadFile(),
    SearchFiles(),
    WriteTextFile(),
    AppendTextFile(),
    DeletePath(),
    CreateFolder(),
    MovePath(),
    # 노트
    ListNotes(),
    ReadNote(),
    WriteNote(),
    AppendNote(),
    DeleteNote(),
    RenameNote(),
    SearchNotes(),
    NoteBacklinks(),
    # 캘린더
    ListCalendarEvents(),
    CreateCalendarEvent(),
    UpdateCalendarEvent(),
    DeleteCalendarEvent(),
    FindFreeSlots(),
    # 시스템
    GetSystemStatus(),
]

__all__ = [
    "ALL_SKILLS",
    "ThinkSkill", "ListFiles", "ReadFile", "SearchFiles", "WriteTextFile",
    "AppendTextFile", "DeletePath", "CreateFolder", "MovePath",
    "ListNotes", "ReadNote", "WriteNote", "AppendNote", "DeleteNote",
    "RenameNote", "SearchNotes", "NoteBacklinks",
    "ListCalendarEvents", "CreateCalendarEvent", "UpdateCalendarEvent",
    "DeleteCalendarEvent", "FindFreeSlots", "GetSystemStatus",
]
