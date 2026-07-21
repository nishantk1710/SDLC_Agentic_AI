"""Centralized LLM communication.

All agents call the LLM through this gateway — never the provider SDK directly.
This keeps prompt execution, retries, logging, and provider choice in one place.

Two providers are supported, selected by ``LLM_PROVIDER`` (see app/config/settings.py):

* ``anthropic``    — Claude Messages API (default). Uses ``ANTHROPIC_API_KEY`` + ``LLM_MODEL``.
* ``azure_openai`` — Azure OpenAI Chat Completions. Uses the ``AZURE_OPENAI_*`` settings; the
                     *deployment name* is the model id sent to the API.

Both providers expose the SAME surface — :meth:`complete` and :meth:`complete_with_tools`, each
returning text — so no agent changes when the provider changes. The provider-specific SDK is the
only thing that differs, and it lives entirely inside this file (the ``openai`` import is lazy so
the package is only required when that provider is actually selected).
"""

import json
import logging
from collections import deque
from collections.abc import Callable
from typing import Any

import anthropic

from app.config.settings import get_settings

logger = logging.getLogger(__name__)

#: Value of ``LLM_PROVIDER`` that selects Azure OpenAI.
_AZURE = "azure_openai"


def _loads_tool_args(raw: str | None) -> dict[str, Any]:
    """Parse an OpenAI tool call's ``arguments`` (a JSON string) into a dict; {} on anything odd."""
    try:
        obj = json.loads(raw or "{}")
    except (ValueError, TypeError):
        return {}
    return obj if isinstance(obj, dict) else {}


class LLMGateway:
    """Thin wrapper over the configured LLM provider (Anthropic or Azure OpenAI)."""

    def __init__(self) -> None:
        settings = get_settings()
        self._provider = (settings.llm_provider or "anthropic").strip().lower()
        self._max_tokens = settings.llm_max_tokens

        # Anthropic
        self._model = settings.llm_model
        self._api_key = settings.anthropic_api_key or None
        self._use_thinking = settings.llm_thinking

        # Azure OpenAI
        self._azure_api_key = settings.azure_openai_api_key or None
        self._azure_endpoint = settings.azure_openai_endpoint or None
        self._azure_api_version = settings.azure_openai_api_version
        self._azure_deployment = settings.azure_openai_deployment
        self._azure_use_max_completion = settings.azure_openai_use_max_completion_tokens

        # Build the client lazily (see _get_client). A provider SDK raises at construction if no
        # key is resolvable, so constructing it here would make merely importing this module
        # require credentials — breaking app boot and tests when none are set.
        self._client: Any | None = None

    # ----------------------------------------------------------------- client
    def _get_client(self) -> Any:
        """Create the provider client on first use."""
        if self._client is not None:
            return self._client
        if self._provider == _AZURE:
            if not self._azure_endpoint or not self._azure_deployment:
                raise RuntimeError(
                    "llm_provider=azure_openai requires AZURE_OPENAI_ENDPOINT and "
                    "AZURE_OPENAI_DEPLOYMENT to be set (see .env.example)."
                )
            from openai import AzureOpenAI  # lazy: openai is only needed for this provider

            self._client = AzureOpenAI(
                api_key=self._azure_api_key,
                api_version=self._azure_api_version,
                azure_endpoint=self._azure_endpoint,
            )
        else:
            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    @property
    def _model_id(self) -> str:
        """Model id used in API calls + logs (the deployment name for Azure)."""
        return self._azure_deployment if self._provider == _AZURE else self._model

    # ----------------------------------------------------------------- complete
    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Run a single prompt and return the model's text response."""
        if self._provider == _AZURE:
            return self._complete_openai(prompt, system=system, max_tokens=max_tokens)
        return self._complete_anthropic(prompt, system=system, max_tokens=max_tokens)

    def _complete_anthropic(
        self, prompt: str, *, system: str | None = None, max_tokens: int | None = None
    ) -> str:
        kwargs: dict = {
            "model": self._model,
            "max_tokens": max_tokens or self._max_tokens,
            "system": system or anthropic.NOT_GIVEN,
            "messages": [{"role": "user", "content": prompt}],
        }
        # Adaptive thinking is only supported on Claude 4.6+ models. Disable it
        # via LLM_THINKING=false if LLM_MODEL points at a model without it.
        if self._use_thinking:
            kwargs["thinking"] = {"type": "adaptive"}

        response = self._get_client().messages.create(**kwargs)
        self._log_usage(response.usage.input_tokens, response.usage.output_tokens)
        return "".join(block.text for block in response.content if block.type == "text")

    def _openai_token_kwarg(self, n: int) -> dict[str, int]:
        """Reasoning models (gpt-5/o-series) require ``max_completion_tokens``; older ones take
        ``max_tokens``. Controlled by ``AZURE_OPENAI_USE_MAX_COMPLETION_TOKENS`` (default true)."""
        key = "max_completion_tokens" if self._azure_use_max_completion else "max_tokens"
        return {key: n}

    def _complete_openai(
        self, prompt: str, *, system: str | None = None, max_tokens: int | None = None
    ) -> str:
        response = self._get_client().chat.completions.create(
            model=self._model_id,
            messages=self._openai_messages(prompt, system),
            **self._openai_token_kwarg(max_tokens or self._max_tokens),
        )
        usage = getattr(response, "usage", None)
        self._log_usage(
            getattr(usage, "prompt_tokens", "?"), getattr(usage, "completion_tokens", "?")
        )
        return response.choices[0].message.content or ""

    # ----------------------------------------------------------------- tools
    def complete_with_tools(
        self,
        prompt: str,
        *,
        system: str | None = None,
        tools: list | None = None,
        max_iters: int = 4,
    ) -> str:
        """Tool-augmented completion: bind ``tools`` to the model and run a tool-use loop.

        The tool binding + provider SDK usage live HERE (the single door) so callers like the
        repair node never import the SDK. Each tool may be a repair-tool wrapper (with a
        ``handler``) or a LangChain tool (with ``invoke``). Returns the model's final text
        (which carries the proposed fix). Falls back to :meth:`complete` when no tools are given.
        """
        if not tools:
            return self.complete(prompt, system=system)
        if self._provider == _AZURE:
            return self._complete_with_tools_openai(
                prompt, system=system, tools=tools, max_iters=max_iters
            )
        return self._complete_with_tools_anthropic(
            prompt, system=system, tools=tools, max_iters=max_iters
        )

    def _complete_with_tools_anthropic(
        self, prompt: str, *, system: str | None, tools: list, max_iters: int
    ) -> str:
        client = self._get_client()
        specs = [self._anthropic_tool_spec(tool) for tool in tools]
        by_name = {getattr(tool, "name", ""): tool for tool in tools}
        messages: list = [{"role": "user", "content": prompt}]
        final_text = ""
        for _ in range(max_iters):
            kwargs: dict = {
                "model": self._model,
                "max_tokens": self._max_tokens,
                "messages": messages,
                "tools": specs,
            }
            if system:
                kwargs["system"] = system
            response = client.messages.create(**kwargs)
            final_text = "".join(b.text for b in response.content if getattr(b, "type", None) == "text")
            tool_uses = [b for b in response.content if getattr(b, "type", None) == "tool_use"]
            if not tool_uses:
                return final_text
            messages.append({"role": "assistant", "content": response.content})
            results = [
                {"type": "tool_result", "tool_use_id": tu.id, "content": str(self._run_tool(by_name.get(tu.name), tu.input))}
                for tu in tool_uses
            ]
            messages.append({"role": "user", "content": results})
        return final_text

    def _complete_with_tools_openai(
        self, prompt: str, *, system: str | None, tools: list, max_iters: int
    ) -> str:
        client = self._get_client()
        specs = [self._openai_tool_spec(tool) for tool in tools]
        by_name = {getattr(tool, "name", ""): tool for tool in tools}
        messages = self._openai_messages(prompt, system)
        final_text = ""
        for _ in range(max_iters):
            response = client.chat.completions.create(
                model=self._model_id,
                messages=messages,
                tools=specs,
                **self._openai_token_kwarg(self._max_tokens),
            )
            message = response.choices[0].message
            final_text = message.content or ""
            tool_calls = getattr(message, "tool_calls", None)
            if not tool_calls:
                return final_text
            messages.append(self._openai_assistant_message(message, tool_calls))
            for call in tool_calls:
                args = _loads_tool_args(call.function.arguments)
                result = self._run_tool(by_name.get(call.function.name), args)
                messages.append({"role": "tool", "tool_call_id": call.id, "content": str(result)})
        return final_text

    # ----------------------------------------------------------------- helpers
    @staticmethod
    def _openai_messages(prompt: str, system: str | None) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return messages

    @staticmethod
    def _openai_assistant_message(message: Any, tool_calls: Any) -> dict[str, Any]:
        """Rebuild the assistant turn (content + tool_calls) to send back into the loop."""
        return {
            "role": "assistant",
            "content": message.content or "",
            "tool_calls": [
                {
                    "id": c.id,
                    "type": "function",
                    "function": {"name": c.function.name, "arguments": c.function.arguments},
                }
                for c in tool_calls
            ],
        }

    @staticmethod
    def _anthropic_tool_spec(tool: Any) -> dict:
        """Build an Anthropic tool spec from a repair-tool wrapper or a LangChain tool."""
        schema = getattr(tool, "input_schema", None)
        if schema is None:
            args_schema = getattr(tool, "args_schema", None)
            try:
                schema = args_schema.model_json_schema() if args_schema is not None else {"type": "object", "properties": {}}
            except Exception:  # noqa: BLE001
                schema = {"type": "object", "properties": {}}
        return {"name": getattr(tool, "name", ""), "description": getattr(tool, "description", ""), "input_schema": schema}

    @classmethod
    def _openai_tool_spec(cls, tool: Any) -> dict:
        """Build an OpenAI function-tool spec (reuses the Anthropic schema extraction)."""
        spec = cls._anthropic_tool_spec(tool)
        return {
            "type": "function",
            "function": {
                "name": spec["name"],
                "description": spec["description"],
                "parameters": spec["input_schema"] or {"type": "object", "properties": {}},
            },
        }

    @staticmethod
    def _run_tool(tool: Any, tool_input: Any) -> Any:
        """Dispatch a model tool-call to the underlying tool implementation."""
        if tool is None:
            return "unknown tool"
        if hasattr(tool, "handler"):
            return tool.handler(**tool_input) if isinstance(tool_input, dict) else tool.handler(tool_input)
        if hasattr(tool, "invoke"):
            return tool.invoke(tool_input)
        return "tool is not callable"

    def _log_usage(self, input_tokens: Any, output_tokens: Any) -> None:
        logger.info(
            "llm_call provider=%s model=%s input_tokens=%s output_tokens=%s",
            self._provider,
            self._model_id,
            input_tokens,
            output_tokens,
        )


# Module-level singleton so agents share one client / connection pool.
llm_gateway = LLMGateway()


class FakeLLMGateway(LLMGateway):
    """Deterministic test double with the same ``.complete(prompt, system=...)`` surface.

    Subclasses :class:`LLMGateway` (so it can be injected wherever one is expected) but does NOT
    call the real ``__init__`` — no settings, API key, or network. Configure with a list of
    responses (returned in order) OR a callable ``(prompt) -> str``. Every call is recorded in
    :attr:`calls`. Used by tests / conftest (DEVELOPER_GUIDE.md §8).
    """

    def __init__(  # noqa: D401  # intentionally does not call super().__init__()
        self,
        responses: list[str] | Callable[[str], str] | None = None,
        *,
        default: str | None = None,
    ) -> None:
        self._responder: Callable[[str], str] | None = responses if callable(responses) else None
        self._queue: deque[str] = deque([] if callable(responses) else (responses or []))
        self._default = default
        self.calls: list[dict[str, Any]] = []

    def complete(self, prompt: str, *, system: str | None = None, **kwargs: Any) -> str:
        self.calls.append({"prompt": prompt, "system": system, "kwargs": kwargs})
        if self._responder is not None:
            return self._responder(prompt)
        if self._queue:
            return self._queue.popleft()
        if self._default is not None:
            return self._default
        raise IndexError("FakeLLMGateway ran out of scripted responses and no default was set")

    def complete_with_tools(
        self,
        prompt: str,
        *,
        system: str | None = None,
        tools: list | None = None,
        max_iters: int = 4,
    ) -> str:
        # Deterministic double: ignore tools, return the next scripted response.
        # TODO: to catch accidental misuse (repair path calling the wrong method), tests could
        # script a distinct response here vs. complete() and assert which one was served.
        return self.complete(prompt, system=system)
