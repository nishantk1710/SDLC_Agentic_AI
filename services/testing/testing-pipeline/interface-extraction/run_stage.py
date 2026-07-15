"""Standalone runner for the Interface Extraction stage (dev/debug).

Runs Stage A against whatever the Source Loader Service has placed under
``data/input`` and prints a summary. Useful without spinning up the FastAPI app.

    # from services/testing/testing-pipeline/interface-extraction/
    python run_stage.py            # real LLM for A3 (needs TESTING_LLM_API_KEY)
    python run_stage.py --mock     # offline: inject a canned A3 reply
"""

from __future__ import annotations

import argparse
import json
import logging

from interface_extraction import run_interface_extraction


def _mock_llm(_messages):
    return json.dumps(
        {
            "test_files_impacted": [],
            "test_coverage_impact": "(mock run — no LLM called)",
            "historical_test_risks": "",
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Interface Extraction (Stage A).")
    parser.add_argument("--mock", action="store_true", help="Use a canned A3 reply (no API key).")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s [%(name)s] %(message)s")

    result = run_interface_extraction(llm=_mock_llm if args.mock else None)
    print(json.dumps({"summary": result["summary"], "artifacts": result["artifacts"]}, indent=2))


if __name__ == "__main__":
    main()
