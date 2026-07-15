"""Minimal LLM client for Stage B's direct-LLM planner.

Same shape as Stage A's client (a ``(messages) -> str`` callable, lazy litellm
import, env-based creds via ``TESTING_LLM_``). It is duplicated per-stage to keep
stages self-contained on the shared ``sys.path`` (no cross-stage imports).

FUTURE: once ``packages/`` is fleshed out, lift this and Stage A's client into a
single shared ``packages/llm`` module and have both stages import it.
"""

from __future__ import annotations

import logging
from typing import Callable, Dict, List

from tcd_config import LLMSettings, llm_settings

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
                "No TESTING_LLM_API_KEY set. Add it to .env, or inject a fake LLM."
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
            kwargs["api_base"] = self.cfg.base_url.rstrip("/")

        logger.info("Stage B LLM call: model=%s", self.cfg.model)
        try:
            response = completion(**kwargs)
        except Exception as exc:
            logger.error("Stage B LLM call failed: %s", exc)
            raise
        content = response["choices"][0]["message"]["content"]
        logger.info("Stage B LLM call ok: %d chars", len(content or ""))
        return content


def get_default_llm() -> LLMCallable:
    return LLMClient().complete
