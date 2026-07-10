"""Centralized LLM communication.

All agents call the LLM through this gateway — never the provider SDK directly.
This keeps prompt execution, retries, logging, and provider choice in one place.
"""

import logging
from collections import deque
from collections.abc import Callable
from typing import Any

import anthropic

from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class LLMGateway:
    """Thin wrapper over the Anthropic Messages API."""

    def __init__(self) -> None:
        settings = get_settings()
        self._model = settings.llm_model
        self._max_tokens = settings.llm_max_tokens
        self._api_key = settings.anthropic_api_key or None
        self._use_thinking = settings.llm_thinking
        # Build the client lazily (see _get_client). The Anthropic SDK raises
        # at construction if no key is resolvable, so constructing it here would
        # make merely importing this module require an API key — breaking app
        # boot and tests when no key is set.
        self._client: anthropic.Anthropic | None = None

    def _get_client(self) -> anthropic.Anthropic:
        """Create the Anthropic client on first use."""
        if self._client is None:
            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Run a single prompt and return the model's text response."""
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
        logger.info(
            "llm_call model=%s input_tokens=%s output_tokens=%s",
            self._model,
            response.usage.input_tokens,
            response.usage.output_tokens,
        )
        return "".join(
            block.text for block in response.content if block.type == "text"
        )

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

        client = self._get_client()
        specs = [self._tool_spec(tool) for tool in tools]
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

    @staticmethod
    def _tool_spec(tool: Any) -> dict:
        """Build an Anthropic tool spec from a repair-tool wrapper or a LangChain tool."""
        schema = getattr(tool, "input_schema", None)
        if schema is None:
            args_schema = getattr(tool, "args_schema", None)
            try:
                schema = args_schema.model_json_schema() if args_schema is not None else {"type": "object", "properties": {}}
            except Exception:  # noqa: BLE001
                schema = {"type": "object", "properties": {}}
        return {"name": getattr(tool, "name", ""), "description": getattr(tool, "description", ""), "input_schema": schema}

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
