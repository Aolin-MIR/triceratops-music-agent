"""Intent router for the chat-first REAPER music agent."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class RouteDecision:
    intent: str
    reply: str
    needs_generation: bool = False
    use_selection: bool = False


CONTROL_PATTERNS = {
    "cancel": r"\b(cancel|stop|abort)\b|取消|停止|别生成",
    "undo": r"\b(undo|revert)\b|撤销|退回",
    "accept": r"\b(accept|keep|approve)\b|接受|保留|采用",
    "reject": r"\b(reject|discard)\b|拒绝|丢弃|不要这个版本",
    "status": r"\b(status|progress|what.*doing)\b|进度|状态|在干嘛",
}
REVISION_PATTERN = re.compile(
    r"\b(revise|modify|change|extend|shorten|selected|selection|chorus|verse|drums?|bass|melody)\b|"
    r"修改|改成|选中|延长|缩短|副歌|主歌|鼓|贝斯|旋律|不要改",
    re.IGNORECASE,
)


def _heuristic(message: str, has_selection: bool) -> RouteDecision | None:
    for intent, pattern in CONTROL_PATTERNS.items():
        if re.search(pattern, message, re.IGNORECASE):
            replies = {
                "cancel": "I’ll cancel the active generation and keep the model warm.",
                "undo": "I’ll ask REAPER to undo the last Triceratops import.",
                "accept": "I’ll keep the current MIDI version.",
                "reject": "I’ll reject this version and undo its import.",
                "status": "I’ll report the current agent state.",
            }
            return RouteDecision(intent, replies[intent])
    if has_selection and REVISION_PATTERN.search(message):
        return RouteDecision("revise", "I’ll analyze the selected MIDI and create a revision candidate.",
                             needs_generation=True, use_selection=True)
    return None


def route_intent(message: str, *, has_selection: bool, busy_state: str = "") -> RouteDecision:
    """Classify one conversational turn, with deterministic control safeguards."""
    direct = _heuristic(message, has_selection)
    if direct:
        return direct
    if busy_state in {"planning", "loading_model", "sampling", "verifying", "converting", "correcting"}:
        return RouteDecision("status", "The agent is already working. You can ask for status or cancel it.")
    key = os.environ.get("QWEN_API_KEY")
    if key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=key,
                            base_url=os.environ.get("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
                            timeout=30.0, max_retries=1)
            response = client.chat.completions.create(
                model=os.environ.get("QWEN_MODEL", "qwen-plus"),
                messages=[
                    {"role": "system", "content": (
                        "Route a REAPER music-agent message. Return JSON only with intent and reply. "
                        "intent must be generate or revise. Choose revise only when the user requests changing, "
                        "extending, preserving, or restyling existing material and a MIDI selection exists. "
                        "Otherwise choose generate. reply is one concise sentence describing the action."
                    )},
                    {"role": "user", "content": json.dumps(
                        {"message": message, "midi_selection_available": has_selection}, ensure_ascii=False)},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            payload = json.loads(response.choices[0].message.content or "{}")
            intent = payload.get("intent")
            if intent in {"generate", "revise"}:
                use_selection = intent == "revise" and has_selection
                return RouteDecision(intent, str(payload.get("reply") or "I’ll work on that."),
                                     needs_generation=True, use_selection=use_selection)
        except Exception:
            pass
    return RouteDecision("generate", "I’ll create a new MIDI version from your request and project context.",
                         needs_generation=True)
