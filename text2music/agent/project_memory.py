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
        if not needle:
            raise ValueError("Specify the memory fact to remove")
        after = [item for item in before if needle not in str(item.get("fact", "")).casefold()]
        data["facts"] = after
        self._save(data)
        return {"removed": len(before) - len(after)}

    def update(self, text: str, fact: str, category: str = "constraint") -> dict[str, Any]:
        needle, replacement = text.casefold().strip(), fact.strip()
        if not needle or not replacement:
            raise ValueError("Updating memory requires an existing fact and its replacement")
        data = self.load()
        matches = [item for item in data.get("facts", [])
                   if needle in str(item.get("fact", "")).casefold()]
        if len(matches) != 1:
            raise ValueError("Memory update must identify exactly one existing fact")
        previous = matches[0]["fact"]
        matches[0].update(fact=replacement, category=category, updated=time.time())
        self._save(data)
        return {"updated_from": previous, "remembered": replacement, "category": category}

    def update_music_context(self, updates: dict[str, Any], source: str) -> dict[str, Any]:
        # Validate using the same public tool schema before touching storage.
        from text2music.agent.direct_actions import validate_arguments
        validate_arguments("update_music_context", {"updates": updates})
        if not source.strip():
            raise ValueError("Musical context needs its original user request")
        data = self.load()
        current = data.setdefault("music_context", {})
        revision = int(data.get("music_revision", 0)) + 1
        previous = {key: current.get(key) for key in updates}
        for key, value in updates.items():
            if value is None:
                current.pop(key, None)
                continue
            current[key] = {"value": value, "source": source, "revision": revision, "updated": time.time()}
        data["music_revision"] = revision
        audit = data.setdefault("music_updates", [])
        audit.append({"revision": revision, "previous": previous, "updates": updates, "source": source})
        self._save(data)
        return {"music_context": {k: v["value"] for k, v in current.items()}, "revision": revision}

    def music_context(self) -> dict[str, Any]:
        return {k: v["value"] for k, v in self.load().get("music_context", {}).items()}

    def context(self, *, include_summary: bool = True) -> str:
        data = self.load()
        facts = data.get("facts", [])[-30:]
        summary = str(data.get("conversation_summary", "")).strip() if include_summary else ""
        lines = [f"- [{item.get('category', 'fact')}] {item.get('fact', '')}" for item in facts]
        music = self.music_context()
        return "\n".join((["Active musical requirements (authoritative; omitted fields are cleared or unset): " + json.dumps(music, ensure_ascii=False)] if music or data.get("music_revision") else []) + (["Project memory:", *lines] if lines else []) +
                         (["Conversation summary: " + summary] if summary else []))

    def recall(self, text: str) -> dict[str, Any]:
        needle = text.casefold().strip()
        facts = [item for item in self.load().get("facts", [])
                 if needle in str(item.get("fact", "")).casefold()]
        return {"facts": facts, "music_context": self.music_context(),
                "music_revision": self.load().get("music_revision", 0), "storage_path": str(self.path)}

    def set_summary(self, summary: str) -> None:
        data = self.load()
        data["conversation_summary"] = summary.strip()[-6000:]
        self._save(data)

    def _save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)
