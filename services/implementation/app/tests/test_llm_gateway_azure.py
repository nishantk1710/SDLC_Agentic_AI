"""Azure OpenAI provider path — unit tests.

These drive the REAL gateway code (``_complete_openai`` / ``_complete_with_tools_openai`` / the
OpenAI tool-spec + tool-loop) against a fake client that mimics the ``openai.AzureOpenAI`` response
shape. No API key, no network — so they run under ``pytest -m "not integration"`` like the rest.

What they prove: given ``LLM_PROVIDER=azure_openai``, the gateway (a) targets the deployment as the
model id, (b) builds system+user chat messages, (c) emits OpenAI *function* tool specs, and (d)
runs the tool-use loop — invoking the handler with the model's args and feeding the result back.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from app.services.llm_gateway import LLMGateway


# --------------------------------------------------------------------------- fake openai client


def _text_response(text: str) -> SimpleNamespace:
    """A chat completion with plain text and no tool calls."""
    message = SimpleNamespace(content=text, tool_calls=None)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message)],
        usage=SimpleNamespace(prompt_tokens=11, completion_tokens=22),
    )


def _tool_call_response(name: str, args: dict) -> SimpleNamespace:
    """A chat completion asking to call ``name`` with ``args`` (arguments are a JSON string)."""
    call = SimpleNamespace(id="call_1", function=SimpleNamespace(name=name, arguments=json.dumps(args)))
    message = SimpleNamespace(content=None, tool_calls=[call])
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message)],
        usage=SimpleNamespace(prompt_tokens=11, completion_tokens=22),
    )


class _FakeCompletions:
    def __init__(self, responses: list) -> None:
        self._responses = list(responses)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


class _FakeAzureClient:
    """Mimics ``openai.AzureOpenAI``: exposes ``.chat.completions.create(**kwargs)``."""

    def __init__(self, responses: list) -> None:
        self.chat = SimpleNamespace(completions=_FakeCompletions(responses))


def _azure_gateway(client: _FakeAzureClient) -> LLMGateway:
    """A gateway forced onto the Azure path with the fake client injected (no real settings/key)."""
    gw = LLMGateway()
    gw._provider = "azure_openai"
    gw._azure_deployment = "gpt-4o-mydeploy"
    gw._client = client
    return gw


# --------------------------------------------------------------------------- complete()


def test_azure_complete_returns_text_and_targets_the_deployment() -> None:
    client = _FakeAzureClient([_text_response("hello from azure")])
    gw = _azure_gateway(client)

    out = gw.complete("hi there", system="be concise")

    assert out == "hello from azure"
    sent = client.chat.completions.calls[0]
    assert sent["model"] == "gpt-4o-mydeploy"  # deployment name is the model id
    assert sent["messages"] == [
        {"role": "system", "content": "be concise"},
        {"role": "user", "content": "hi there"},
    ]


def test_azure_complete_omits_system_when_none() -> None:
    client = _FakeAzureClient([_text_response("ok")])
    gw = _azure_gateway(client)

    gw.complete("just a user turn")

    messages = client.chat.completions.calls[0]["messages"]
    assert messages == [{"role": "user", "content": "just a user turn"}]  # no system message


# --------------------------------------------------------------------------- complete_with_tools()


def test_azure_tool_loop_invokes_handler_then_returns_text() -> None:
    # Round 1: model asks to call read_file. Round 2: model returns final text.
    client = _FakeAzureClient(
        [
            _tool_call_response("read_file", {"path": "p1/gulpfile.js"}),
            _text_response("fixed it"),
        ]
    )
    gw = _azure_gateway(client)

    seen: dict[str, str] = {}

    def read_file(path: str) -> str:
        seen["path"] = path
        return "file contents"

    tool = SimpleNamespace(
        name="read_file",
        description="read a file",
        input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
        handler=read_file,
    )

    out = gw.complete_with_tools("fix it", system="sys", tools=[tool])

    assert out == "fixed it"
    assert seen["path"] == "p1/gulpfile.js"  # handler ran with the model's args

    first, second = client.chat.completions.calls
    # tool advertised in OpenAI function shape
    assert first["tools"][0]["type"] == "function"
    assert first["tools"][0]["function"]["name"] == "read_file"
    assert first["tools"][0]["function"]["parameters"]["properties"] == {"path": {"type": "string"}}
    # the tool result was fed back on the second turn
    roles = [m["role"] for m in second["messages"]]
    assert roles[-2:] == ["assistant", "tool"]
    assert second["messages"][-1] == {
        "role": "tool",
        "tool_call_id": "call_1",
        "content": "file contents",
    }


def test_azure_complete_with_tools_without_tools_falls_back_to_complete() -> None:
    client = _FakeAzureClient([_text_response("plain answer")])
    gw = _azure_gateway(client)

    out = gw.complete_with_tools("hello", tools=None)

    assert out == "plain answer"
    # single, tool-less chat call
    assert len(client.chat.completions.calls) == 1
    assert "tools" not in client.chat.completions.calls[0]


def test_azure_uses_max_completion_tokens_by_default() -> None:
    # Reasoning models (gpt-5/o-series) require max_completion_tokens; that is the default.
    client = _FakeAzureClient([_text_response("x")])
    gw = _azure_gateway(client)

    gw.complete("hi")

    sent = client.chat.completions.calls[0]
    assert "max_completion_tokens" in sent
    assert "max_tokens" not in sent


def test_azure_can_fall_back_to_max_tokens_when_configured() -> None:
    client = _FakeAzureClient([_text_response("x")])
    gw = _azure_gateway(client)
    gw._azure_use_max_completion = False  # e.g. an old deployment/API version

    gw.complete("hi")

    sent = client.chat.completions.calls[0]
    assert "max_tokens" in sent
    assert "max_completion_tokens" not in sent


def test_azure_missing_endpoint_raises_clear_error() -> None:
    gw = LLMGateway()
    gw._provider = "azure_openai"
    gw._azure_endpoint = None
    gw._azure_deployment = "gpt-4o"
    gw._client = None  # force real client construction path

    try:
        gw.complete("hi")
        raise AssertionError("expected a RuntimeError for missing endpoint")
    except RuntimeError as exc:
        assert "AZURE_OPENAI_ENDPOINT" in str(exc)
