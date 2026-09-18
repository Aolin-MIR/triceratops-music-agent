import json
from pathlib import Path

from text2music.agent.knowledge import KnowledgeBase
from text2music.agent.project_memory import ProjectMemory, project_key
from text2music.agent.tool_loop import DESCRIPTIONS, tool_schemas
from text2music.agent.vst_service import _windows_path
from text2music.agent import vst_service


def test_knowledge_rebuild_search_and_source_citation(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    source = docs / "arrangement.md"
    source.write_text("Rock arrangements use a bass part and drum backbeat. 摇滚编曲需要鼓和贝斯。", encoding="utf-8")
    knowledge = KnowledgeBase(tmp_path / "index.json", [docs])
    assert knowledge.rebuild() == {"sources": 1, "chunks": 1}
    results = knowledge.search("摇滚 鼓 贝斯")
    assert results
    assert results[0]["source"] == str(source.resolve())
    assert "摇滚" in results[0]["text"]
    source.write_text("Jazz arrangements often use extended harmony.", encoding="utf-8")
    assert knowledge.search("extended harmony")[0]["source"] == str(source.resolve())


def test_project_memory_is_scoped_deduplicated_and_forgettable(tmp_path: Path):
    assert project_key({"project_path": "E:\\Music\\Demo.rpp"}) == "e-music-demo.rpp"
    memory = ProjectMemory(tmp_path, "demo")
    memory.remember("Keep the melody", "constraint")
    memory.remember("Keep the melody", "constraint")
    assert memory.context().count("Keep the melody") == 1
    assert memory.forget("melody") == {"removed": 1}
    assert "Keep the melody" not in memory.context()


def test_foundation_tools_have_strict_schemas():
    assert {"search_knowledge", "remember_fact", "forget_fact", "list_capabilities"} <= set(DESCRIPTIONS)
    schemas = {item["function"]["name"]: item["function"]["parameters"] for item in tool_schemas()}
    assert schemas["search_knowledge"]["properties"]["limit"]["maximum"] == 10
    assert schemas["remember_fact"]["additionalProperties"] is False


def test_windows_path_is_not_corrupted_when_already_native():
    assert _windows_path(Path("E:\\Music\\clip.mid")) == "E:\\Music\\clip.mid"


def test_service_start_resets_stale_status(tmp_path, monkeypatch):
    status = tmp_path / "status.txt"
    status.write_text("STATE: planning\nPROGRESS: 15\n", encoding="utf-8")
    monkeypatch.setattr(vst_service, "STATUS", status)
    vst_service._write_status("ready", "0", "Service ready")
    assert vst_service._read_status()["state"] == "ready"
