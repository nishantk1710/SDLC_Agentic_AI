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
        # The SDK reads ANTHROPIC_API_KEY from the environment; pass it
        # explicitly so it also works when loaded from .env via settings.
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key or None)

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Run a single prompt and return the model's text response.

        Uses adaptive thinking, which is recommended for Claude 4.6+ models.
        """
        response = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens or self._max_tokens,
            thinking={"type": "adaptive"},
            system=system or anthropic.NOT_GIVEN,
            messages=[{"role": "user", "content": prompt}],
        )
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
