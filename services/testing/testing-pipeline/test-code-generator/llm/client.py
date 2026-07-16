"""
client.py — Anthropic-API-compatible wrapper for Step C's code generation calls.

Calls a Claude deployment hosted through Azure AI Foundry via the native
`anthropic` SDK, pointed at Azure's endpoint via `base_url` --
`BASE_URL` here ends in `/anthropic/`, which is Azure's own
Anthropic-API-compatible route for Claude deployments, not an
OpenAI-compatible one.

History, for context on why this isn't the OpenAI-based client that was
here before: attempts against `AzureOpenAI` (classic deployment-path
routing) and plain `OpenAI` with a `{endpoint}/openai/v1/` base_url both
returned 404s (`api_not_supported`, `DeploymentNotFound`) against this
resource's `.openai.azure.com` domain. Once the actual endpoint turned out
to be a *different* domain (`.services.ai.azure.com`) with an `/anthropic/`
path, it became clear this deployment is served via Azure's native
Anthropic-compatible route, not any OpenAI-shaped one -- hence using the
`anthropic` SDK's own request/response format (system prompt as a
top-level param, `tool_use` content blocks, `x-api-key` auth) instead of
OpenAI's tool-calling format.

Forces structured output via tool-use (no markdown-fence parsing) and pins
deterministic settings (temperature 0) so regeneration is close to
reproducible despite being LLM-driven, not template-driven.

`anthropic` is imported lazily inside functions, not at module level, so
this module (and anything that imports it) stays importable in tests that
mock generate_structured() without needing the real package installed.

Reads AZURE_OPENAI_API_KEY / BASE_URL / DEFAULT_MODEL / LLM_MAX_TOKENS from
the environment, loading a local .env file first if one exists (see
.env.example in this directory for the required keys).
"""

import os

from dotenv import load_dotenv

load_dotenv()  # populates os.environ from a local .env, if present; no-ops otherwise

DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL", "claude-sonnet-4-6")
MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", "8192"))
_TOOL_NAME = "emit_generated_file"
_MAX_ATTEMPTS = 2


def generate_structured(system_prompt: str, user_prompt: str, output_schema: dict) -> dict:
    """Call the LLM, forcing it to respond via a single tool call matching
    output_schema. Returns the tool call's input dict. Retries once on a
    non-conforming/refused response before raising -- never silently
    degrades to parsing freeform text."""
    import anthropic

    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    base_url = os.environ.get("BASE_URL")
    if not api_key:
        raise RuntimeError("AZURE_OPENAI_API_KEY is not set")
    if not base_url:
        raise RuntimeError("BASE_URL is not set")

    client = anthropic.Anthropic(api_key=api_key, base_url=base_url)

    tool = {
        "name": _TOOL_NAME,
        "description": "Emit the generated test file as structured data.",
        "input_schema": output_schema,
    }
    messages = [{"role": "user", "content": user_prompt}]

    for attempt in range(_MAX_ATTEMPTS):
        response = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=MAX_TOKENS,
            temperature=0,
            system=system_prompt,
            tools=[tool],
            tool_choice={"type": "tool", "name": _TOOL_NAME},
            messages=messages,
        )
        for block in response.content:
            if block.type == "tool_use" and block.name == _TOOL_NAME:
                return block.input

        messages.append({"role": "assistant", "content": response.content})
        messages.append({
            "role": "user",
            "content": f"You must respond by calling the {_TOOL_NAME} tool. Try again.",
        })

    raise RuntimeError(f"LLM did not return a {_TOOL_NAME!r} tool call after {_MAX_ATTEMPTS} attempts")
