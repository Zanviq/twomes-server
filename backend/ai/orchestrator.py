"""ReAct 오케스트레이터 — 스킬을 연속 실행하며 추론.

LLM이 function_call(스킬 호출)을 내면 디스패치하고 결과(observation)를
대화에 추가해 다음 스텝으로 넘긴다. 텍스트 응답이 나오면 종료.
LLM 객체는 주입 가능(테스트에서 가짜 LLM 사용).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Iterator

from ..config import Settings
from .prompt_builder import build_system
from .skill_base import SkillContext
from .skill_registry import SkillRegistry, default_registry

logger = logging.getLogger("twoems.ai")


@dataclass
class LLMResult:
    text: str
    tool_use: dict | None  # {"name": str, "args": dict}


class GeminiLLM:
    """google-genai(신 SDK) 기반 function-calling LLM."""

    def __init__(self, settings: Settings):
        self._settings = settings

    def chat(self, contents: list[dict], catalog: list[dict], system: str) -> LLMResult:
        from google import genai
        from google.genai import types

        if not self._settings.gemini_api_key:
            return LLMResult(text="GEMINI_API_KEY가 설정되지 않았습니다 (.env 확인).", tool_use=None)

        client = genai.Client(api_key=self._settings.gemini_api_key)
        config = types.GenerateContentConfig(
            system_instruction=system,
            tools=[types.Tool(function_declarations=catalog)] if catalog else None,
        )
        try:
            resp = client.models.generate_content(
                model=self._settings.gemini_model, contents=contents, config=config
            )
        except Exception as e:  # noqa: BLE001
            logger.exception("Gemini 호출 실패")
            return LLMResult(text=f"LLM 오류: {e}", tool_use=None)

        text, tool_use = "", None
        cand = resp.candidates[0] if resp.candidates else None
        if cand and cand.content and cand.content.parts:
            for part in cand.content.parts:
                fc = getattr(part, "function_call", None)
                if fc and fc.name:
                    tool_use = {"name": fc.name, "args": dict(fc.args) if fc.args else {}}
                    break
                if getattr(part, "text", ""):
                    text += part.text
        return LLMResult(text=text, tool_use=tool_use)


def run(
    user,
    settings: Settings,
    message: str,
    today: str,
    llm=None,
    registry: SkillRegistry | None = None,
    history: list[dict] | None = None,
) -> Iterator[dict]:
    """ReAct 루프 실행. 이벤트 dict를 순차적으로 yield.

    이벤트: {type: tool_call|tool_result|text|done|error, ...}
    """
    registry = registry or default_registry()
    llm = llm or GeminiLLM(settings)
    ctx = SkillContext(user=user, settings=settings)
    catalog = registry.build_catalog()
    system = build_system(user, _tone(user, settings), today)

    contents: list[dict] = list(history or [])
    contents.append({"role": "user", "parts": [{"text": message}]})

    max_steps = max(1, min(16, settings.ai_max_steps))
    final_text = ""

    for step in range(max_steps):
        result = llm.chat(contents, catalog, system)

        if result.tool_use:
            name = result.tool_use["name"]
            args = result.tool_use.get("args", {})
            yield {"type": "tool_call", "name": name, "args": args}

            skill_result = registry.dispatch(name, args, ctx)
            yield {
                "type": "tool_result",
                "name": name,
                "ok": skill_result.ok,
                "message": skill_result.message,
            }

            # 모델의 호출 + 결과(observation)를 대화에 추가
            contents.append({"role": "model", "parts": [{"function_call": {"name": name, "args": args}}]})
            contents.append(
                {
                    "role": "user",
                    "parts": [
                        {
                            "function_response": {
                                "name": name,
                                "response": {
                                    "ok": skill_result.ok,
                                    "message": skill_result.message,
                                    "data": skill_result.data,
                                },
                            }
                        }
                    ],
                }
            )
            continue

        final_text = result.text
        break
    else:
        final_text = final_text or "최대 단계에 도달했습니다."

    yield {"type": "text", "text": final_text}
    yield {"type": "done"}


def _tone(user, settings: Settings) -> str:
    try:
        from .. import user_settings

        return user_settings.load(user, settings).get("ai", {}).get("tone", "assistant")
    except Exception:  # noqa: BLE001
        return "assistant"


def sse_format(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
