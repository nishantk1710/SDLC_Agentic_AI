"""Centralized LLM communication.

All agents call the LLM through this gateway — never the provider SDK directly.
This keeps prompt execution, retries, logging, and provider choice in one place.
"""

import logging

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


# Module-level singleton so agents share one client / connection pool.
llm_gateway = LLMGateway()
