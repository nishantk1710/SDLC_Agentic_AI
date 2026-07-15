"""Standalone runner for the Test-Case Derivation stage (dev/debug).

Consumes Stage A's artifacts under ``data/`` and writes ``data/test-cases.json``.

    # from services/testing/testing-pipeline/test-case-derivation/
    python run_stage.py            # real LLM (needs TESTING_LLM_API_KEY)
    python run_stage.py --mock     # offline: canned test cases, no API key
    python run_stage.py --no-cache # bypass the derivation cache
"""

from __future__ import annotations

import argparse
import json
import logging

from test_case_derivation import run_test_case_derivation


def _mock_llm(_messages):
    return json.dumps(
        {
            "test_cases": [
                {
                    "id": "TC-000-1",
                    "req_id": "",
                    "type": "happy_path",
                    "input": {},
                    "expected": {},
                    "notes": "(mock run — no LLM called)",
                    "target_symbols": [],
                }
            ]
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Test-Case Derivation (Stage B).")
    parser.add_argument("--mock", action="store_true", help="Use canned cases (no API key).")
    parser.add_argument("--no-cache", action="store_true", help="Bypass the derivation cache.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s [%(name)s] %(message)s")

    result = run_test_case_derivation(
        llm=_mock_llm if args.mock else None,
        use_cache=not args.no_cache,
    )
    print(json.dumps({"summary": result["summary"], "artifacts": result["artifacts"]}, indent=2))


if __name__ == "__main__":
    main()
