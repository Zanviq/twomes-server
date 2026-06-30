"""기본 스킬 모음. 모두 SkillContext의 사용자 스코프 안에서만 동작."""
from __future__ import annotations

from ... import calendar_store
from ...gemini_client import TEXT_EXTENSIONS
from ...security_paths import safe_join, to_rel
from ...storage import notes_root, resolve, scope_root
from ..skill_base import SkillBase, SkillResult

_SCOPE_PROP = {
    "type": "string",
    "enum": ["common", "me"],
    "description": "common=공통 공간, me=내 개인 공간",
}
_MAX_READ = 20000


# ── 사고/계획 ──
class ThinkSkill(SkillBase):
    name = "think"
    description = "복잡한 작업 전에 계획을 정리한다. 데이터를 바꾸지 않으며, 여러 스킬을 순서대로 쓸 때 먼저 호출."
    parameters = {
        "type": "object",
        "properties": {"reasoning": {"type": "string", "description": "수행 계획과 이유"}},
        "required": ["reasoning"],
    }

    def run(self, args, ctx):
        return SkillResult(ok=True, message="사고 완료", data={"reasoning": args.get("reasoning", "")})


# ── 파일 ──
class ListFiles(SkillBase):
    name = "list_files"
    description = "지정한 공간/폴더의 파일·폴더 목록을 본다."
    parameters = {
        "type": "object",
        "properties": {
            "scope": _SCOPE_PROP,
            "path": {"type": "string", "description": "스코프 루트 기준 상대 폴더 (기본 루트)"},
        },
        "required": ["scope"],
    }

    def run(self, args, ctx):
        root = scope_root(args["scope"], ctx.user, ctx.settings)
        target = resolve(args["scope"], args.get("path", ""), ctx.user, ctx.settings)
        if not target.exists() or not target.is_dir():
            return SkillResult(ok=False, message="폴더를 찾을 수 없습니다.", error_code="not_found")
        items = [
            {"name": c.name, "path": to_rel(root, c), "is_dir": c.is_dir()}
            for c in sorted(target.iterdir())
        ]
        return SkillResult(ok=True, message=f"{len(items)}개 항목", data={"items": items})


class ReadFile(SkillBase):
    name = "read_file"
    description = "텍스트 파일의 내용을 읽는다(.md/.txt/코드 등). 민감 파일은 차단됨."
    parameters = {
        "type": "object",
        "properties": {"scope": _SCOPE_PROP, "path": {"type": "string"}},
        "required": ["scope", "path"],
    }

    def run(self, args, ctx):
        target = resolve(args["scope"], args["path"], ctx.user, ctx.settings)
        if not target.exists() or not target.is_file():
            return SkillResult(ok=False, message="파일을 찾을 수 없습니다.", error_code="not_found")
        if target.suffix.lower() not in TEXT_EXTENSIONS:
            return SkillResult(ok=False, message="텍스트 파일만 읽을 수 있습니다.", error_code="unsupported")
        text = target.read_text(encoding="utf-8", errors="replace")[:_MAX_READ]
        return SkillResult(ok=True, message="읽기 완료", data={"content": text})


class SearchFiles(SkillBase):
    name = "search_files"
    description = "파일명에 키워드가 포함된 파일을 찾는다."
    parameters = {
        "type": "object",
        "properties": {"scope": _SCOPE_PROP, "query": {"type": "string"}},
        "required": ["scope", "query"],
    }

    def run(self, args, ctx):
        root = scope_root(args["scope"], ctx.user, ctx.settings)
        q = args["query"].lower()
        hits = [
            to_rel(root, p)
            for p in root.rglob("*")
            if p.is_file() and q in p.name.lower()
        ][:50]
        return SkillResult(ok=True, message=f"{len(hits)}개 검색됨", data={"matches": hits})


# ── 노트 ──
class ListNotes(SkillBase):
    name = "list_notes"
    description = "노트 목록을 본다."
    parameters = {"type": "object", "properties": {"scope": _SCOPE_PROP}, "required": ["scope"]}

    def run(self, args, ctx):
        root = notes_root(args["scope"], ctx.user, ctx.settings)
        titles = [p.stem for p in sorted(root.rglob("*.md")) if p.is_file()]
        return SkillResult(ok=True, message=f"{len(titles)}개 노트", data={"notes": titles})


class ReadNote(SkillBase):
    name = "read_note"
    description = "제목으로 노트 내용을 읽는다."
    parameters = {
        "type": "object",
        "properties": {"scope": _SCOPE_PROP, "title": {"type": "string"}},
        "required": ["scope", "title"],
    }

    def run(self, args, ctx):
        root = notes_root(args["scope"], ctx.user, ctx.settings)
        target = safe_join(root, f"{args['title']}.md")
        if not target.exists():
            return SkillResult(ok=False, message="노트를 찾을 수 없습니다.", error_code="not_found")
        return SkillResult(
            ok=True,
            message="읽기 완료",
            data={"content": target.read_text(encoding="utf-8", errors="replace")[:_MAX_READ]},
        )


class WriteNote(SkillBase):
    name = "write_note"
    description = "노트를 만들거나 덮어쓴다(마크다운, [[위키링크]] 가능)."
    mutating = True
    parameters = {
        "type": "object",
        "properties": {
            "scope": _SCOPE_PROP,
            "title": {"type": "string"},
            "content": {"type": "string"},
        },
        "required": ["scope", "title", "content"],
    }

    def run(self, args, ctx):
        root = notes_root(args["scope"], ctx.user, ctx.settings)
        target = safe_join(root, f"{args['title']}.md")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(args["content"], encoding="utf-8")
        return SkillResult(ok=True, message=f"노트 '{args['title']}' 저장됨", data={"title": args["title"]})


# ── 캘린더 (스케줄링) ──
class ListCalendarEvents(SkillBase):
    name = "list_calendar_events"
    description = "기간 내 일정을 조회한다(스케줄 충돌 확인 등)."
    parameters = {
        "type": "object",
        "properties": {
            "from_date": {"type": "string", "description": "ISO 날짜/시간 (예: 2026-07-01)"},
            "to_date": {"type": "string"},
        },
    }

    def run(self, args, ctx):
        events = calendar_store.list_events(
            ctx.user, ctx.settings, args.get("from_date"), args.get("to_date")
        )
        return SkillResult(ok=True, message=f"{len(events)}개 일정", data={"events": events})


class CreateCalendarEvent(SkillBase):
    name = "create_calendar_event"
    description = "새 일정(이벤트)을 만든다. 사용자가 일정을 잡아달라고 하면 사용."
    mutating = True
    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "start": {"type": "string", "description": "ISO 시작 (예: 2026-07-02T14:00:00)"},
            "end": {"type": "string", "description": "ISO 종료"},
            "all_day": {"type": "boolean"},
            "description": {"type": "string"},
            "color": {"type": "string", "description": "Google colorId 1~11"},
        },
        "required": ["title", "start"],
    }

    def run(self, args, ctx):
        ev = calendar_store.create_event(
            ctx.user,
            ctx.settings,
            {
                "title": args["title"],
                "start": args["start"],
                "end": args.get("end", args["start"]),
                "allDay": bool(args.get("all_day", False)),
                "description": args.get("description", ""),
                "color": args.get("color", "2"),
            },
        )
        return SkillResult(ok=True, message=f"일정 '{ev['title']}' 생성됨", data={"event": ev})
