"""사고/계획 스킬."""
from __future__ import annotations

from ..skill_base import SkillBase, SkillResult


class ThinkSkill(SkillBase):
    name = "think"
    description = (
        "복잡한 작업 전에 계획을 정리한다. 데이터를 바꾸지 않으며, "
        "여러 스킬을 순서대로 써야 할 때 먼저 호출해 단계를 세운다."
    )
    parameters = {
        "type": "object",
        "properties": {"reasoning": {"type": "string", "description": "수행 계획과 이유"}},
        "required": ["reasoning"],
    }

    def run(self, args, ctx):
        return SkillResult(ok=True, message="사고 완료", data={"reasoning": args.get("reasoning", "")})
