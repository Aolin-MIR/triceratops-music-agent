"""Synchronous project-bank client for the native Hindsight daemon.

The service handles multiple HTTP worker threads, so each call uses a plain
short-lived request instead of sharing Hindsight's event-loop-bound SDK client.
"""
from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import ProxyHandler, Request, build_opener


class HindsightHTTPError(RuntimeError):
    def __init__(self, status: int, detail: str) -> None:
        self.status = status
        super().__init__(f"Hindsight HTTP {status}: {detail}")


class HindsightStore:
    def __init__(self, base_url: str, bank_id: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.bank_id = bank_id
        self.root = f"/v1/default/banks/{quote(bank_id, safe='')}"
        self.opener = build_opener(ProxyHandler({}))
        self.ensure_bank()

    def ensure_bank(self) -> None:
        try:
            self.request("GET", self.root + "/config")
        except HindsightHTTPError as exc:
            if exc.status != 404:
                raise
            self.request("PUT", self.root, {"name": "Triceratops project memory"})

    def request(self, method: str, path: str, body: dict | None = None) -> dict:
        request = Request(self.base_url + path,
                          data=json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None,
                          headers={"Accept": "application/json", "Content-Type": "application/json"},
                          method=method)
        try:
            with self.opener.open(request, timeout=180) as response:
                result = json.load(response)
        except HTTPError as exc:
            detail = exc.read(512).decode("utf-8", errors="replace")
            raise HindsightHTTPError(exc.code, detail) from exc
        except (URLError, TimeoutError) as exc:
            raise RuntimeError("Hindsight memory service is unavailable") from exc
        if not isinstance(result, dict):
            raise RuntimeError("Hindsight returned an invalid response")
        return result

    def retain(self, document_id: str, content: str, category: str) -> None:
        result = self.request("POST", self.root + "/memories", {
            "items": [{"content": content, "document_id": document_id,
                       "context": "Triceratops project requirement",
                       "metadata": {"category": category}}], "async": False})
        if result.get("success") is not True or result.get("items_count") != 1:
            raise RuntimeError("Hindsight did not retain the project requirement")
        # Upstream can report a successful request without storing a document.
        saved = self.document(document_id)
        if saved.get("original_text") != content:
            raise RuntimeError("Hindsight did not persist the project requirement")

    def delete(self, document_id: str) -> None:
        result = self.request("DELETE", self.root + "/documents/" + quote(document_id, safe=""))
        if result.get("success") is not True:
            raise RuntimeError("Hindsight did not delete the project requirement")

    def documents(self) -> list[dict]:
        documents = []
        offset = 0
        while True:
            page = self.request("GET", self.root + f"/documents?limit=100&offset={offset}")
            items = page.get("items")
            if not isinstance(items, list):
                raise RuntimeError("Hindsight document listing is invalid")
            for item in items:
                document_id = item.get("id", "")
                if isinstance(document_id, str) and document_id.startswith("triceratops-fact-"):
                    documents.append(self.document(document_id))
            offset += len(items)
            if offset >= int(page.get("total", -1)):
                return documents
            if not items:
                raise RuntimeError("Hindsight document pagination is incomplete")

    def document(self, document_id: str) -> dict:
        return self.request("GET", self.root + "/documents/" + quote(document_id, safe=""))

    def recall(self, query: str, *, max_tokens: int = 768) -> list[dict]:
        result = self.request("POST", self.root + "/memories/recall", {
            "query": query, "max_tokens": max_tokens, "budget": "low"})
        items = result.get("results")
        if not isinstance(items, list):
            raise RuntimeError("Hindsight recall result is invalid")
        return items
