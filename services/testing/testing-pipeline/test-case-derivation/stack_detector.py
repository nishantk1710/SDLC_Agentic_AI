"""Detect the tech stack of the code under test (Stage B, tech-stack agnostic).

Produces a :class:`StackProfile` used to (a) select a generation handler and
(b) parameterize the LLM-fallback prompt, so Stage B never assumes a language.

Detection is layered, most-trusted first:
  1. explicit ``tech_stack`` metadata from the pipeline (Stage A infers this),
  2. the dominant per-symbol ``language`` in the A2 mapping tree,
  3. a safe ``unknown`` default (still handled by the generic handler).

**Extensible by data, not code:** adding a stack = adding a row to
``_LANG_ALIASES`` / ``_FRAMEWORK_KIND`` / ``_TEST_PROFILE``. ``detect_stack``
itself does not change.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

# --- detection rules (extend by adding rows) --------------------------------

# Normalize assorted runtime/language labels to a canonical language.
_LANG_ALIASES = {
    "py": "python", "python": "python", "python3": "python",
    "js": "javascript", "javascript": "javascript", "node": "javascript", "nodejs": "javascript",
    "express": "javascript",
    "ts": "typescript", "typescript": "typescript",
    "java": "java",
    "react": "javascript",  # framework captured separately
}

# framework -> backend|frontend
_FRAMEWORK_KIND = {
    "fastapi": "backend", "flask": "backend", "django": "backend",
    "express": "backend", "spring": "backend", "springboot": "backend",
    "react": "frontend", "angular": "frontend", "vue": "frontend", "svelte": "frontend",
}

# (language, framework) -> (test_framework, conventions for the LLM prompt).
# framework "" is the language default. First exact match wins, else language default.
_TEST_PROFILE = {
    ("python", ""): ("pytest", "Use pytest; call code in-process; use @pytest.mark.parametrize for input variants."),
    ("python", "fastapi"): ("pytest", "Use pytest + FastAPI/Starlette TestClient (in-process); parametrize; assert status_code and JSON body."),
    ("python", "flask"): ("pytest", "Use pytest + Flask test_client(); assert status code and JSON body."),
    ("python", "django"): ("pytest", "Use pytest-django (or Django TestCase); assert response status and content."),
    ("javascript", ""): ("jest", "Use jest; assert with expect()."),
    ("javascript", "express"): ("jest", "Use jest + supertest for HTTP endpoints; assert status and body."),
    ("javascript", "react"): ("jest + React Testing Library", "Use jest + React Testing Library (jsdom); render, query by role/text, assert on the DOM; mock fetch/network."),
    ("typescript", ""): ("jest (ts-jest)", "Use jest with ts-jest; expect() assertions."),
    ("typescript", "express"): ("jest + supertest", "Use jest + supertest; assert status and typed body."),
    ("typescript", "react"): ("jest + React Testing Library", "Use jest + RTL (.tsx, jsdom); mock network."),
    ("java", ""): ("JUnit 5", "Use JUnit 5 (assertEquals/assertThrows) with Mockito for mocks."),
    ("java", "spring"): ("JUnit 5 + Spring Test", "Use JUnit 5 + Spring Boot Test / MockMvc; assert HTTP status and body."),
}

_BACKEND_LANGS = {"python", "java"}


@dataclass
class StackProfile:
    """Resolved stack of the code under test."""

    language: str = "unknown"      # python | javascript | typescript | java | unknown
    framework: str = ""            # fastapi | express | react | spring | ...
    kind: str = "unknown"          # backend | frontend | unknown
    test_framework: str = ""       # pytest | jest | JUnit 5 | ...
    conventions: str = ""          # short guidance injected into the LLM prompt
    detected_from: str = ""        # tech_stack | mapping_tree | default

    @property
    def key(self) -> str:
        """Handler-selection key (the canonical language)."""
        return self.language or "unknown"

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def describe(self) -> str:
        parts = [self.language]
        if self.framework:
            parts.append(self.framework)
        if self.kind and self.kind != "unknown":
            parts.append(self.kind)
        return " / ".join(p for p in parts if p) or "unknown"


def _dominant_language(mapping_tree: Optional[Dict[str, Any]]) -> str:
    symbols = (mapping_tree or {}).get("symbols", {}) or {}
    langs = Counter(
        (node.get("language") or "").lower()
        for node in symbols.values()
        if node.get("language")
    )
    if not langs:
        return ""
    return _LANG_ALIASES.get(langs.most_common(1)[0][0], langs.most_common(1)[0][0])


def detect_stack(
    tech_stack: Optional[Dict[str, Any]] = None,
    mapping_tree: Optional[Dict[str, Any]] = None,
    requirements: Optional[List[Dict[str, Any]]] = None,
) -> StackProfile:
    """Resolve a :class:`StackProfile` from pipeline signals (see module doc)."""
    ts = tech_stack or {}

    raw = str(ts.get("language") or ts.get("runtime") or "").strip().lower()
    language = _LANG_ALIASES.get(raw, raw)
    detected_from = "tech_stack" if language else ""

    if not language:
        language = _dominant_language(mapping_tree)
        detected_from = "mapping_tree" if language else ""

    if not language:
        language, detected_from = "unknown", "default"

    framework = str(ts.get("framework") or "").strip().lower()
    if not framework and raw in ("express", "react", "fastapi", "flask", "django", "angular", "vue"):
        framework = raw  # runtime token doubled as a framework name

    kind = str(ts.get("kind") or "").strip().lower() or _FRAMEWORK_KIND.get(framework, "")
    if not kind:
        kind = "backend" if language in _BACKEND_LANGS else "unknown"

    test_framework, conventions = (
        _TEST_PROFILE.get((language, framework))
        or _TEST_PROFILE.get((language, ""))
        or ("", "Use the language's standard unit-test framework and idiomatic assertions.")
    )

    return StackProfile(
        language=language,
        framework=framework,
        kind=kind,
        test_framework=test_framework,
        conventions=conventions,
        detected_from=detected_from,
    )
