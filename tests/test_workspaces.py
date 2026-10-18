import json
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import pytest
from text2music.agent import vst_service as svc
from text2music.agent.project_memory import ProjectMemory, project_key
from text2music.agent.workspaces import workspace_scope


@pytest.fixture
def workspace_api(tmp_path, monkeypatch):
    monkeypatch.delenv("TRICERATOPS_CONFIG", raising=False)
    monkeypatch.setattr(svc, "RUNS_DIR", tmp_path)
    root = svc.TriceratopsState()
    monkeypatch.setattr(svc, "APP", root)
    server = ThreadingHTTPServer(("127.0.0.1", 0), svc.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    def post(path, payload):
        req = Request(
            f"http://127.0.0.1:{server.server_port}" + path,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            r = urlopen(req, timeout=5)
        except HTTPError as e:
            r = e
        with r:
            return r.status, json.load(r)

    yield root, post
    server.shutdown()
    server.server_close()


def test_full_project_identity_cannot_collide_on_sanitizing_or_truncated_prefix():
    prefix = "E:/Music/" + "a" * 100
    assert project_key({"project_path": prefix + "one.rpp"}) != project_key(
        {"project_path": prefix + "two.rpp"}
    )
    assert project_key({"project_path": "E:/Music/One.rpp"}) == project_key(
        {"project_path": "e:\\music\\one.rpp"}
    )
    assert project_key({"workspace_id": "one"}) != project_key({"project_path": "/one"})
    with pytest.raises(ValueError, match="identity is missing"):
        project_key({"name": "VST3"})


def test_projects_separate_chat_memory_results_history_cancel_and_import(workspace_api):
    root, post = workspace_api
    host_a = {"project_path": "E:/Music/a.rpp"}
    host_b = {"project_path": "E:/Music/b.rpp"}
    assert post("/session/open", {"session": "a", "host": host_a})[0] == 200
    assert post("/session/open", {"session": "b", "host": host_b})[0] == 200
    a = root.for_request({"session": "a"})
    b = root.for_request({"session": "b"})
    a.append_turn("user", "Only project A: no drums.")
    b.append_turn("user", "Only project B: percussion allowed.")
    a.last_result = {"midi": "A.mid"}
    a.last_reply = "A result"
    b.last_result = {"midi": "B.mid"}
    b.last_reply = "B result"
    ma = ProjectMemory(a.storage_root, a.workspace_id)
    mb = ProjectMemory(b.storage_root, b.workspace_id)
    ma.remember("Only A constraint")
    mb.remember("Only B constraint")
    ma.update_music_context({"tempo": 93, "style": "distant piano"}, "A request")
    mb.update_music_context({"tempo": 140}, "B request")
    assert ma.recall("")["facts"][0]["fact"] == "Only A constraint"
    assert mb.music_context() == {"tempo": 140}
    reopened = post("/session/open", {"session":"reopened-a", "host":host_a})[1]
    assert [turn["content"] for turn in reopened["conversation"]] == ["Only project A: no drums."]
    assert "Only project B" not in json.dumps(reopened)
    assert post("/session/ping", {"session": "a"})[1]["result"]["midi"] == "A.mid"
    assert post("/session/ping", {"session": "b"})[1]["result"]["midi"] == "B.mid"
    assert post("/cancel", {"session": "b"})[0] == 200
    assert b.cancel_event.is_set() and not a.cancel_event.is_set()
    _, prepared = post("/prepare_import_reaper", {"session": "a", "file": "A.mid"})
    assert (
        post(
            "/import_reaper_receipt",
            {"session": "b", "request_id": prepared["request_id"]},
        )[0]
        == 409
    )
    assert post("/chat/clear", {"session": "a"})[0] == 200
    with workspace_scope(a.storage_root):
        assert svc._conversation_history() == []
    with workspace_scope(b.storage_root):
        assert (
            svc._conversation_history()[0]["content"]
            == "Only project B: percussion allowed."
        )
    assert b.last_result["midi"] == "B.mid"
    # Same project in another editor and another model uses the same state/store.
    assert root.for_request({"session": "another", "host": host_a}) is a
    assert ProjectMemory(a.storage_root, a.workspace_id).music_context()["tempo"] == 93
    # An explicit workspace is stable when the host cannot supply its path.
    x = root.for_request(
        {"session": "au-midi", "host": {"workspace_id": "shared-logic-project"}}
    )
    assert (
        root.for_request(
            {"session": "au-audio", "host": {"workspace_id": "shared-logic-project"}}
        )
        is x
    )
    assert x is not a and x is not b


def test_unknown_project_has_no_implicit_global_chat_or_memory(workspace_api):
    root, post = workspace_api
    assert (
        post("/session/open", {"session": "missing", "host": {"name": "VST3"}})[0]
        == 400
    )
    assert post("/session/open", {"session": "missing"})[0] == 400
    assert not root.workspaces


def test_workspace_context_is_request_local_across_threads(workspace_api):
    root, _ = workspace_api
    a = root.for_request({"session": "a", "host": {"workspace_id": "a"}})
    b = root.for_request({"session": "b", "host": {"workspace_id": "b"}})
    barrier = threading.Barrier(2)

    def write(state, text):
        with workspace_scope(state.storage_root):
            barrier.wait()
            for i in range(10):
                state.append_turn("user", f"{text} {i}")

    one = threading.Thread(target=write, args=(a, "alpha"))
    two = threading.Thread(target=write, args=(b, "beta"))
    one.start()
    two.start()
    one.join()
    two.join()
    with workspace_scope(a.storage_root):
        assert all("alpha" in h["content"] for h in svc._conversation_history())
    with workspace_scope(b.storage_root):
        assert all("beta" in h["content"] for h in svc._conversation_history())
