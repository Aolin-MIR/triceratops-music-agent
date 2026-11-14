import pytest


class MemoryBank:
    """In-memory Hindsight HTTP contract for tests that do not need the daemon."""

    def __init__(self):
        self.items = {}

    def retain(self, document_id, content, category):
        self.items[document_id] = {"id": document_id, "original_text": content,
                                   "metadata": {"category": category}}

    def delete(self, document_id):
        del self.items[document_id]

    def documents(self):
        return list(self.items.values())

    def recall(self, query, *, max_tokens=768):
        return [{"text": item["original_text"]} for item in self.items.values()
                if any(word in item["original_text"].casefold() for word in query.casefold().split())]


@pytest.fixture
def fake_hindsight(monkeypatch):
    from text2music.agent import memory_runtime
    banks = {}
    monkeypatch.setattr(memory_runtime, "project_store",
                        lambda key: banks.setdefault(key, MemoryBank()))
    return banks
