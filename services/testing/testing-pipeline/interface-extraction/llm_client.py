"""Minimal LLM client for A3 (Interface Extraction stage).

Credentials come from ``ie_config.LLMSettings`` (env, ``TESTING_LLM_`` prefix) —
never hardcoded. ``litellm`` is imported lazily so A1/A2 and the tests never
require it; only a real A3 call does. The public shape is a callable
``(messages) -> str`` so tests can inject a fake and real runs use
``LLMClient.complete``.
"""

from __future__ import annotations

import logging
from typing import Callable, Dict, List

from ie_config import LLMSettings, llm_settings

logger = logging.getLogger(__name__)

LLMCallable = Callable[[List[Dict[str, str]]], str]


class LLMNotConfigured(RuntimeError):
    """Raised when a real LLM call is attempted without an API key."""


class LLMClient:
    """Thin sync wrapper over LiteLLM's ``completion``."""

    def __init__(self, cfg: LLMSettings | None = None):
        self.cfg = cfg or llm_settings

    def complete(self, messages: List[Dict[str, str]]) -> str:
        if not self.cfg.is_configured:
            raise LLMNotConfigured(
                "No TESTING_LLM_API_KEY set. Add it to .env (see root .env.example), "
                "or inject a fake LLM (tests / mock)."
            )
        try:
            from litellm import completion  # lazy import
        except Exception as exc:  # pragma: no cover - env dependent
            raise RuntimeError(
                "litellm is not installed. Run: pip install -r requirements.txt"
            ) from exc

        kwargs: Dict[str, object] = {
            "model": self.cfg.model,
            "messages": messages,
            "temperature": self.cfg.temperature,
            "timeout": self.cfg.timeout,
        }
        if self.cfg.api_key:
            kwargs["api_key"] = self.cfg.api_key
        if self.cfg.base_url:
            # LiteLLM uses `api_base`; strip trailing slash to avoid a doubled path.
            kwargs["api_base"] = self.cfg.base_url.rstrip("/")

        logger.info("A3 LLM call: model=%s api_base=%s", self.cfg.model, kwargs.get("api_base"))
        try:
            response = completion(**kwargs)
        except Exception as exc:
            logger.error("A3 LLM call failed: %s", exc)
            raise
        content = response["choices"][0]["message"]["content"]
        logger.info("A3 LLM call ok: %d chars", len(content or ""))
        return content


def get_default_llm() -> LLMCallable:
    """Return the default LLM callable built from environment config."""
    return LLMClient().complete
