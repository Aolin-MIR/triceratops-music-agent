"""Explicit cloud/local chat backends. Local models stay on the selected device."""
from __future__ import annotations
import json
import os
import uuid
from dataclasses import dataclass
from types import SimpleNamespace
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, build_opener, ProxyHandler


@dataclass(frozen=True)
class ChatSettings:
    provider: str
    model: str
    base_url: str
    device: str
    timeout: float
    context_size: int

    @classmethod
    def load(cls, provider_override=""):
        import sys
        if provider_override not in {"", "remote", "local"}:
            raise ValueError("Chat selection must be configured default, remote or local")
        provider = ("ollama" if sys.platform == "darwin" else "llama_cpp") if provider_override == "local" else (provider_override or os.environ.get("TRICERATOPS_LLM_PROVIDER", "remote"))
        if provider not in {"remote", "ollama", "llama_cpp", "disabled"}:
            raise ValueError("llm_provider must be remote, ollama, llama_cpp or disabled")
        local = provider in {"ollama", "llama_cpp"}
        device = "gpu" if provider_override == "local" else os.environ.get("TRICERATOPS_LLM_DEVICE", "gpu" if local else "cpu")
        if device not in {"cpu", "gpu"}:
            raise ValueError("llm_device must be cpu or gpu")
        if local and device != "gpu":
            raise ValueError("Local chat requires GPU acceleration. CPU inference is disabled; select a cloud API instead.")
        url = (os.environ.get("TRICERATOPS_OLLAMA_URL", "http://127.0.0.1:11434") if provider == "ollama"
               else os.environ.get("TRICERATOPS_LLAMA_CPP_URL", "http://127.0.0.1:1234/v1") if provider == "llama_cpp"
               else os.environ.get("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"))
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Chat URL must be an HTTP(S) endpoint without embedded credentials")
        if local and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("Local chat servers must use a loopback URL")
        if provider == "ollama" and parsed.path not in {"", "/"}:
            raise ValueError("Ollama must use a loopback URL without a path")
        if provider == "llama_cpp" and parsed.path.rstrip("/") != "/v1":
            raise ValueError("llama.cpp must use its loopback /v1 API URL")
        timeout = float(os.environ.get("TRICERATOPS_LLM_TIMEOUT", "180" if local else "60"))
        context = int(os.environ.get("TRICERATOPS_LLM_CONTEXT", "8192"))
        if not 5 <= timeout <= 900 or not 4096 <= context <= 16384:
            raise ValueError("Chat timeout must be 5..900 seconds; context must be 4096..16384 tokens")
        model = (os.environ.get("TRICERATOPS_LOCAL_MODEL", "qwen3.5:4b-q4_K_M") if local
                 else os.environ.get("QWEN_MODEL", "qwen-plus"))
        if not model.strip():
            raise ValueError("A chat model must be selected")
        return cls(provider, model, url.rstrip("/"), device, timeout, context)


def local_request(settings: ChatSettings, path: str, payload: dict | None = None) -> dict:
    # Never send loopback requests (or local conversation data) through an environment proxy.
    request = Request(settings.base_url + path,
                      data=json.dumps(payload).encode("utf-8") if payload is not None else None,
                      headers={"Content-Type": "application/json"})
    try:
        with build_opener(ProxyHandler({})).open(request, timeout=settings.timeout) as response:
            data = json.load(response)
    except HTTPError as exc:
        detail = exc.read(2048).decode("utf-8", errors="replace")
        raise RuntimeError(f"Ollama HTTP {exc.code}: {detail}") from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError("Cannot reach the selected local Ollama server; start it and check its URL. "
                           "No cloud request or device substitution was made.") from exc
    if not isinstance(data, dict) or data.get("error"):
        raise RuntimeError(f"Ollama returned an error: {data.get('error') if isinstance(data, dict) else 'invalid JSON object'}")
    return data


def server_request(settings: ChatSettings, url: str) -> dict:
    request = Request(url, headers={"Accept": "application/json"})
    try:
        with build_opener(ProxyHandler({})).open(request, timeout=settings.timeout) as response:
            data = json.load(response)
    except HTTPError as exc:
        raise RuntimeError(f"Local inference server HTTP {exc.code}") from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError("Cannot reach the selected local inference server; no cloud request or device substitution was made") from exc
    if not isinstance(data, dict):
        raise RuntimeError("Local inference server returned an invalid response")
    return data


def residency(settings: ChatSettings) -> dict:
    if settings.provider == "llama_cpp":
        root = settings.base_url[:-3].rstrip("/")
        health = server_request(settings, root + "/health")
        if health.get("status") != "ok":
            raise RuntimeError("llama.cpp reports that the model is not resident")
        props = server_request(settings, root + "/props")
        return {"provider": "llama_cpp", "model": props.get("model_alias", settings.model),
                "device": settings.device, "resident": True, "context_length": props.get("default_generation_settings", {}).get("n_ctx")}
    entries = local_request(settings, "/api/ps").get("models", [])
    name = settings.model if ":" in settings.model else settings.model + ":latest"
    entry = next((item for item in entries if item.get("name") in {settings.model, name}
                  or item.get("model") in {settings.model, name}), None)
    if entry is None:
        raise RuntimeError("The selected local model is not resident; no music task was started")
    size, vram = int(entry.get("size", 0)), int(entry.get("size_vram", 0))
    if settings.device == "cpu" and vram != 0:
        raise RuntimeError("Local LLM was configured for CPU but Ollama reports GPU memory use")
    if settings.device == "gpu" and (size <= 0 or vram < size):
        raise RuntimeError("The local LLM does not fully reside on GPU. Free GPU memory or explicitly "
                           "select CPU in configuration; automatic CPU offload is not accepted.")
    return {"provider": "ollama", "model": settings.model, "device": settings.device,
            "size_bytes": size, "vram_bytes": vram, "digest": entry.get("digest", ""),
            "context_length": entry.get("context_length"), "resident": True}


class OllamaClient:
    def __init__(self, settings: ChatSettings):
        self.settings = settings
        self.chat = SimpleNamespace(completions=self)
        self.cancelled = None
        self.last_usage = {}

    def _chat(self, payload):
        # Closing this response cancels the request, not the resident model.
        request = Request(self.settings.base_url + '/api/chat', data=json.dumps(payload).encode(),
                          headers={'Content-Type':'application/json'})
        content, calls, final = [], [], {}
        if self.cancelled and self.cancelled():
            raise RuntimeError('Local chat request cancelled; GPU model remains resident')
        with build_opener(ProxyHandler({})).open(request, timeout=self.settings.timeout) as response:
            for line in response:
                if self.cancelled and self.cancelled():
                    raise RuntimeError('Local chat request cancelled; GPU model remains resident')
                if not line.strip():
                    continue
                item = json.loads(line)
                if item.get('error'):
                    raise RuntimeError('Local chat returned an error: ' + str(item['error']))
                message = item.get('message', {})
                content.append(message.get('content') or '')
                calls.extend(message.get('tool_calls') or [])
                if item.get('done'):
                    final = item
                    break
        self.last_usage = {k:final[k] for k in ('prompt_eval_count','eval_count','total_duration','load_duration') if k in final}
        return {**final, 'message':{'content':''.join(content),'tool_calls':calls}}

    def create(self, *, messages, tools, tool_choice="auto", **unused):
        if tool_choice != "auto":
            raise ValueError("Explicit buttons execute directly; local chat uses automatic native tool calls")
        converted, names = [], {}
        for message in messages:
            item = dict(message)
            if item.get("tool_calls"):
                calls = []
                for call in item["tool_calls"]:
                    function = dict(call["function"])
                    arguments = function["arguments"]
                    function["arguments"] = json.loads(arguments) if isinstance(arguments, str) else arguments
                    names[call["id"]] = function["name"]
                    calls.append({"function": function})
                item["tool_calls"] = calls
            if item.get("role") == "tool":
                item["tool_name"] = names[item.pop("tool_call_id")]
            if item.get("content") is None:
                item["content"] = ""
            converted.append(item)
        data = self._chat({
            "model": self.settings.model, "messages": converted, "tools": tools,
            "stream": True, "think": False, "keep_alive": -1,
            "options": {"temperature": 0.2, "num_ctx": self.settings.context_size,
                        "num_predict": max(64, min(1024, int(unused.get("max_tokens", 1024)))),
                        "num_gpu": 0 if self.settings.device == "cpu" else 999},
        })
        if data.get("done") is not True or data.get("done_reason") == "length":
            raise RuntimeError("Local model response was incomplete; no truncated tool call was executed")
        residency(self.settings)
        from openai.types.chat import ChatCompletionMessage
        raw = data.get("message", {})
        calls = []
        for call in raw.get("tool_calls") or []:
            function = call.get("function", {})
            args = function.get("arguments")
            if not isinstance(args, dict):
                raise ValueError("Ollama tool arguments must be a JSON object")
            calls.append({"id": "local_" + uuid.uuid4().hex, "type": "function",
                          "function": {"name": function.get("name"), "arguments": json.dumps(args)}})
        answer = ChatCompletionMessage(role="assistant", content=raw.get("content") or None,
                                       tool_calls=calls or None)
        return SimpleNamespace(choices=[SimpleNamespace(message=answer)])


def create_chat_client(provider_override=""):
    settings = ChatSettings.load(provider_override)
    if settings.provider == "disabled":
        raise RuntimeError("Chat is disabled. Direct action buttons remain available; select a cloud "
                           "API or local model to use free-form chat.")
    if settings.provider == "llama_cpp":
        root = settings.base_url[:-3].rstrip("/")
        health = server_request(settings, root + "/health")
        if health.get("status") != "ok":
            raise RuntimeError("llama.cpp reports that no local model is loaded")
        props = server_request(settings, root + "/props")
        capabilities = props.get("chat_template_caps", {})
        if not capabilities.get("supports_tools"):
            raise RuntimeError("The selected llama.cpp model template does not support tool calls")
        from openai import OpenAI
        return OpenAI(api_key="local-only", base_url=settings.base_url, timeout=settings.timeout, max_retries=0), settings
    if settings.provider == "ollama":
        metadata = local_request(settings, "/api/show", {"model": settings.model})
        if "tools" not in metadata.get("capabilities", []):
            raise RuntimeError("The selected Ollama model does not declare native tool-call support")
        return OllamaClient(settings), settings
    key = os.environ.get("QWEN_API_KEY", "")
    if not key:
        raise RuntimeError("Cloud chat requires an API key (QWEN_API_KEY). Use direct buttons without a key, "
                           "or explicitly configure a local model.")
    from openai import OpenAI
    return OpenAI(api_key=key, base_url=settings.base_url, timeout=settings.timeout, max_retries=0), settings


def check_chat_backend(provider_override="") -> dict:
    """Test native argument extraction and tool-result replay, without music mutations."""
    settings = ChatSettings.load(provider_override)
    if settings.provider == "disabled":
        return {"provider": "disabled", "direct_buttons": True, "chat": False}
    client, settings = create_chat_client(provider_override)
    schema = {"type": "function", "function": {"name": "compatibility_probe",
              "description": "Read a test value. This does not change files or generate music.",
              "parameters": {"type": "object", "properties": {"value": {"type": "integer"}},
                             "required": ["value"], "additionalProperties": False}}}
    messages = [{"role": "system", "content": "You are testing native function calling. Follow instructions exactly."},
                {"role": "user", "content": "Call compatibility_probe with value 37. Do not answer in text before calling it."}]
    response = client.chat.completions.create(model=settings.model, messages=messages, tools=[schema],
                                            tool_choice="auto", parallel_tool_calls=False, temperature=0.2)
    answer = response.choices[0].message
    calls = answer.tool_calls or []
    if len(calls) != 1 or calls[0].function.name != "compatibility_probe" or json.loads(calls[0].function.arguments) != {"value": 37}:
        raise RuntimeError("Chat compatibility check failed: native tool call or exact arguments missing")
    messages.extend([answer.model_dump(exclude_none=True),
                     {"role": "tool", "tool_call_id": calls[0].id, "content": '{"token":"TRICERATOPS_OK_37"}'},
                     {"role": "user", "content": "The tool is finished. Reply only with its token. Do not call another tool."}])
    result = client.chat.completions.create(model=settings.model, messages=messages, tools=[schema],
                                           tool_choice="auto", parallel_tool_calls=False, temperature=0.2)
    reply = result.choices[0].message
    if reply.tool_calls or (reply.content or "").strip() != "TRICERATOPS_OK_37":
        raise RuntimeError("Chat compatibility check failed: tool-result replay was not respected")
    report = {"provider": settings.provider, "model": settings.model, "native_tools": True,
              "tool_result_replay": True, "chat": True}
    if settings.provider in {"ollama", "llama_cpp"}:
        report.update(residency(settings))
    return report


def main():
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser(description="Install/check the explicitly selected chat backend")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--pull", action="store_true", help="Download the configured local model using Ollama")
    parser.add_argument("--residency", action="store_true", help="Inspect actual fixed-device residency")
    args = parser.parse_args()
    from text2music.agent.runtime import configure
    configure(args.config)
    settings = ChatSettings.load()
    if args.pull:
        if settings.provider != "ollama":
            raise ValueError("--pull requires the explicitly selected ollama provider")
        from dataclasses import replace
        local_request(replace(settings, timeout=900), "/api/pull", {"model": settings.model, "stream": False})
    report = residency(settings) if args.residency else check_chat_backend()
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
