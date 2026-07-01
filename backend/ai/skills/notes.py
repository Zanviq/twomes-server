"""노트 관련 스킬."""
from __future__ import annotations

from ...notes_graph import backlinks_for
from ...security_paths import safe_join, to_rel
from ...storage import notes_root
from ..skill_base import SkillBase, SkillResult
from ._common import _MAX_READ, _SCOPE_PROP, _is_sensitive


def _note_path(args, ctx):
    root = notes_root(args["scope"], ctx.user, ctx.settings)
    return root, safe_join(root, f"{args['title']}.md")


class ListNotes(SkillBase):
    name = "list_notes"
    description = "노트 목록(제목들)을 본다."
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
        if _is_sensitive(args["title"]):
            return SkillResult(ok=False, message="민감 노트로 판단되어 AI 읽기가 차단되었습니다.", error_code="blocked")
        _, target = _note_path(args, ctx)
        if not target.exists():
            return SkillResult(ok=False, message="노트를 찾을 수 없습니다.", error_code="not_found")
        return SkillResult(ok=True, message="읽기 완료", data={"content": target.read_text(encoding="utf-8", errors="replace")[:_MAX_READ]})


class WriteNote(SkillBase):
    name = "write_note"
    description = "노트를 만들거나 덮어쓴다(마크다운, [[위키링크]] 가능)."
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
        _, target = _note_path(args, ctx)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(args["content"], encoding="utf-8")
        return SkillResult(ok=True, message=f"노트 '{args['title']}' 저장됨", data={"title": args["title"]})


class AppendNote(SkillBase):
    name = "append_note"
    description = "기존 노트 끝에 내용을 덧붙인다(없으면 생성). 일지·목록 누적에 유용."
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
        _, target = _note_path(args, ctx)
        target.parent.mkdir(parents=True, exist_ok=True)
        prev = target.read_text(encoding="utf-8", errors="replace") if target.exists() else f"# {args['title']}\n"
        sep = "" if prev.endswith("\n") else "\n"
        target.write_text(prev + sep + args["content"] + "\n", encoding="utf-8")
        return SkillResult(ok=True, message=f"노트 '{args['title']}'에 덧붙임", data={"title": args["title"]})


class DeleteNote(SkillBase):
    name = "delete_note"
    description = "노트를 삭제한다."
    parameters = {
        "type": "object",
        "properties": {"scope": _SCOPE_PROP, "title": {"type": "string"}},
        "required": ["scope", "title"],
    }

    def run(self, args, ctx):
        _, target = _note_path(args, ctx)
        if not target.exists():
            return SkillResult(ok=False, message="노트를 찾을 수 없습니다.", error_code="not_found")
        target.unlink()
        return SkillResult(ok=True, message=f"노트 '{args['title']}' 삭제됨", data={})


class RenameNote(SkillBase):
    name = "rename_note"
    description = "노트 제목을 바꾼다."
    parameters = {
        "type": "object",
        "properties": {
            "scope": _SCOPE_PROP,
            "old_title": {"type": "string"},
            "new_title": {"type": "string"},
        },
        "required": ["scope", "old_title", "new_title"],
    }

    def run(self, args, ctx):
        root = notes_root(args["scope"], ctx.user, ctx.settings)
        src = safe_join(root, f"{args['old_title']}.md")
        dst = safe_join(root, f"{args['new_title']}.md")
        if not src.exists():
            return SkillResult(ok=False, message="노트를 찾을 수 없습니다.", error_code="not_found")
        if dst.exists():
            return SkillResult(ok=False, message="같은 제목의 노트가 이미 있습니다.", error_code="exists")
        src.rename(dst)
        return SkillResult(ok=True, message=f"'{args['old_title']}' → '{args['new_title']}'", data={})


class SearchNotes(SkillBase):
    name = "search_notes"
    description = "노트 제목·내용을 전문 검색한다."
    parameters = {
        "type": "object",
        "properties": {"scope": _SCOPE_PROP, "query": {"type": "string"}},
        "required": ["scope", "query"],
    }

    def run(self, args, ctx):
        root = notes_root(args["scope"], ctx.user, ctx.settings)
        ql = args["query"].lower()
        hits = []
        for p in sorted(root.rglob("*.md")):
            if not p.is_file():
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            if ql in p.stem.lower() or ql in text.lower():
                hits.append({"title": p.stem, "path": to_rel(root, p)})
            if len(hits) >= 30:
                break
        return SkillResult(ok=True, message=f"{len(hits)}개 검색됨", data={"matches": hits})


class NoteBacklinks(SkillBase):
    name = "note_backlinks"
    description = "특정 노트를 가리키는 다른 노트들(백링크)을 찾는다."
    parameters = {
        "type": "object",
        "properties": {"scope": _SCOPE_PROP, "title": {"type": "string"}},
        "required": ["scope", "title"],
    }

    def run(self, args, ctx):
        root = notes_root(args["scope"], ctx.user, ctx.settings)
        return SkillResult(ok=True, message="백링크 조회", data={"backlinks": backlinks_for(root, args["title"])})
