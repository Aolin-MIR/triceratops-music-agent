"""Project-scoped facts, summaries and task state for Triceratops."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any


def project_key(host: dict[str, Any]) -> str:
    identity = str(host.get("project_path") or host.get("project") or host.get("name") or "default")
    key = re.sub(r"[^a-zA-Z0-9_.-]+", "-", identity).strip("-").lower()
    return key[:80] or "default"


class ProjectMemory:
    def __init__(self, root: Path, key: str) -> None:
        self.path = root / "projects" / key / "memory.json"

    def load(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def remember(self, fact: str, category: str = "constraint") -> dict[str, Any]:
        if not fact.strip():
            raise ValueError("Memory fact must not be empty")
        data = self.load()
        facts = data.setdefault("facts", [])
        normalized = fact.strip()
        existing = next((item for item in facts if item.get("fact", "").casefold() == normalized.casefold()), None)
        if existing:
            existing.update(category=category, updated=time.time())
        else:
            facts.append({"fact": normalized, "category": category, "updated": time.time()})
        data["facts"] = facts[-100:]
        self._save(data)
        return {"remembered": normalized, "category": category}

    def forget(self, text: str) -> dict[str, Any]:
        data = self.load()
        before = data.get("facts", [])
        needle = text.casefold().strip()
        after = [item for item in before if needle not in str(item.get("fact", "")).casefold()]
        data["facts"] = after
        self._save(data)
        return {"removed": len(before) - len(after)}

    def context(self) -> str:
        data = self.load()
        facts = data.get("facts", [])[-30:]
        summary = str(data.get("conversation_summary", "")).strip()
        lines = [f"- [{item.get('category', 'fact')}] {item.get('fact', '')}" for item in facts]
        return "\n".join((["Project memory:", *lines] if lines else []) +
                         (["Conversation summary: " + summary] if summary else []))

    def set_summary(self, summary: str) -> None:
        data = self.load()
        data["conversation_summary"] = summary.strip()[-6000:]
        self._save(data)

    def _save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)
