"""Lossless workspace-local tool results with explicit, bounded retrieval."""

from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path


class ToolResultStore:
    def __init__(self, root: Path):
        self.root = root

    def save(self, result) -> dict:
        raw = json.dumps(
            result, ensure_ascii=False, sort_keys=True, default=str
        ).encode("utf-8")
        digest = hashlib.sha256(raw).hexdigest()
        result_id = digest[:24]
        self.root.mkdir(parents=True, exist_ok=True)
        target = self.root / (result_id + ".json")
        if not target.exists():
            temporary = target.with_suffix(".tmp")
            temporary.write_bytes(raw)
            temporary.replace(target)
        fields = {}
        for key, value in (
            result.items() if isinstance(result, dict) else [("value", result)]
        ):
            if isinstance(value, (dict, list)):
                fields[key] = {"type": type(value).__name__, "count": len(value)}
            elif isinstance(value, str) and len(value) > 180:
                fields[key] = {"type": "str", "characters": len(value)}
            else:
                fields[key] = {"value": value}
        return {
            "representation": "full-result-stored-for-retrieval",
            "result_id": result_id,
            "sha256": digest,
            "bytes": len(raw),
            "fields": fields,
            "retrieval": "read_tool_result reads exact fields or array pages. No raw JSON was truncated.",
        }

    def read(
        self, result_id: str, field: str = "", offset: int = 0, limit: int = 32
    ) -> dict:
        if not re.fullmatch(r"[0-9a-f]{24}", result_id):
            raise ValueError("Invalid workspace tool result ID")
        if (
            type(offset) is not int
            or offset < 0
            or type(limit) is not int
            or not 1 <= limit <= 128
        ):
            raise ValueError("Result pages require offset >= 0 and limit 1..128")
        raw = (self.root / (result_id + ".json")).read_bytes()
        if hashlib.sha256(raw).hexdigest()[:24] != result_id:
            raise ValueError("Stored tool result failed its integrity check")
        data = json.loads(raw)
        if not field:
            return self.save(data)
        if not isinstance(data, dict) or field not in data:
            raise ValueError("Requested result field does not exist")
        value = data[field]
        if isinstance(value, list):
            return {
                "result_id": result_id,
                "field": field,
                "offset": offset,
                "total": len(value),
                "has_more": offset + limit < len(value),
                "value": value[offset : offset + limit],
            }
        if offset:
            raise ValueError("Offsets are supported only for array fields")
        return {"result_id": result_id, "field": field, "value": value}
