"""Project-scoped facts, summaries and task state for Triceratops."""
from __future__ import annotations

import json
import hashlib
import re
import time
from pathlib import Path
from typing import Any


def project_key(host: dict[str, Any]) -> str:
    """Hash the full explicit identity; wrapper names are never project IDs."""
    import hashlib
    import ntpath
    import unicodedata
    path = str(host.get("project_path") or "").strip()
    workspace = str(host.get("workspace_id") or "").strip()
    if path:
        # Case-insensitive Windows paths identify one project consistently.
        normalized = ntpath.normcase(ntpath.normpath(path)) if re.match(r"^[A-Za-z]:[\\/]", path) else str(Path(path).expanduser().resolve())
        identity = "project:" + normalized
    elif workspace:
        if len(workspace) > 160:
            raise ValueError("Workspace ID must not exceed 160 characters")
        identity = "workspace:" + unicodedata.normalize("NFC", workspace)
    else:
        raise ValueError("Project identity is missing. Select a persistent workspace inside the plug-in.")
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]


class ProjectMemory:
    def __init__(self, root: Path, key: str, store=None) -> None:
        self.path = root / "projects" / key / "memory.json"
        self.key = key
        self._store_override = store

    def _store(self):
        if self._store_override is not None:
            return self._store_override
        from text2music.agent.memory_runtime import project_store
        return project_store(self.key)

    @staticmethod
    def _document_id(fact: str) -> str:
        return "triceratops-fact-" + hashlib.sha256(fact.casefold().encode("utf-8")).hexdigest()[:32]

    def _facts(self) -> list[dict[str, Any]]:
        store = self._store()
        data = self.load()
        # The source JSON is kept intact until every old fact is confirmed in
        # Hindsight. Fixed IDs make an interrupted migration idempotent.
        legacy = data.get("facts", [])
        if legacy:
            for item in legacy:
                fact = str(item.get("fact", "")).strip()
                if fact:
                    category = str(item.get("category", "constraint"))
                    content = json.dumps({"fact": fact, "category": category}, ensure_ascii=False)
                    store.retain(self._document_id(fact), content, category)
            data.pop("facts")
            self._save(data)
        facts = []
        for document in store.documents():
            content = document.get("original_text")
            if not isinstance(content, str):
                raise RuntimeError("Hindsight project fact has no source text")
            item = json.loads(content)
            if not isinstance(item, dict) or not isinstance(item.get("fact"), str):
                raise RuntimeError("Hindsight project fact has invalid source text")
            facts.append({"id": document["id"], "fact": item["fact"],
                          "category": item.get("category", "constraint"),
                          "updated": document.get("updated_at")})
        return facts

    def load(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        if not isinstance(data, dict):
            raise ValueError("Project music state must be a JSON object")
        return data

    def remember(self, fact: str, category: str = "constraint") -> dict[str, Any]:
        if not fact.strip():
            raise ValueError("Memory fact must not be empty")
        normalized = fact.strip()
        existing = next((item for item in self._facts() if item["fact"].casefold() == normalized.casefold()), None)
        document_id = existing["id"] if existing else self._document_id(normalized)
        content = json.dumps({"fact": normalized, "category": category}, ensure_ascii=False)
        self._store().retain(document_id, content, category)
        return {"remembered": normalized, "category": category}

    def forget(self, text: str) -> dict[str, Any]:
        needle = text.casefold().strip()
        if not needle:
            raise ValueError("Specify the memory fact to remove")
        matches = [item for item in self._facts() if needle in item["fact"].casefold()]
        for item in matches:
            self._store().delete(item["id"])
        return {"removed": len(matches)}

    def update(self, text: str, fact: str, category: str = "constraint") -> dict[str, Any]:
        needle, replacement = text.casefold().strip(), fact.strip()
        if not needle or not replacement:
            raise ValueError("Updating memory requires an existing fact and its replacement")
        matches = [item for item in self._facts() if needle in item["fact"].casefold()]
        if len(matches) != 1:
            raise ValueError("Memory update must identify exactly one existing fact")
        previous = matches[0]["fact"]
        content = json.dumps({"fact": replacement, "category": category}, ensure_ascii=False)
        self._store().retain(matches[0]["id"], content, category)
        return {"updated_from": previous, "remembered": replacement, "category": category}

    def update_music_context(self, updates: dict[str, Any], source: str) -> dict[str, Any]:
        # Validate using the same public tool schema before touching storage.
        from text2music.agent.direct_actions import validate_arguments
        validate_arguments("update_music_context", {"updates": updates, "next_action": "finish"})
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

    def context(self, *, include_summary: bool = True, query: str = "") -> str:
        data = self.load()
        facts = self._facts()
        summary = str(data.get("conversation_summary", "")).strip() if include_summary else ""
        lines = [f"- [{item.get('category', 'fact')}] {item.get('fact', '')}" for item in facts]
        music = self.music_context()
        recalled = self._store().recall(query) if query.strip() and facts else []
        relevant = [str(item.get("text", "")) for item in recalled if item.get("text")]
        return "\n".join((["Active musical requirements (authoritative; omitted fields are cleared or unset): " + json.dumps(music, ensure_ascii=False)] if music or data.get("music_revision") else []) + (["Project memory:", *lines] if lines else []) +
                         (["Relevant recalled memory:", *relevant] if relevant else []) +
                         (["Conversation summary: " + summary] if summary else []))

    def recall(self, text: str) -> dict[str, Any]:
        needle = text.casefold().strip()
        facts = [item for item in self._facts() if not needle or needle in item["fact"].casefold()]
        return {"facts": facts, "music_context": self.music_context(),
                "music_revision": self.load().get("music_revision", 0),
                "semantic_matches": self._store().recall(text) if needle else []}

    def set_summary(self, summary: str) -> None:
        data = self.load()
        data["conversation_summary"] = summary.strip()
        self._save(data)

    def _save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)
