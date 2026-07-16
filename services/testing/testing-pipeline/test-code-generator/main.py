"""
main.py — Step C's CLI entrypoint. Wires dispatcher -> validators -> writer
into one runnable command:

    python main.py --input services/testing/data/test_cases.json \\
                    --output services/testing/data/generated_tests/

Registers every generator (Python, Node, and React are real; E2E is still
a Phase 6 stub) with the dispatcher, then runs the full pipeline:
load+validate test_cases.json, resolve tech stack, generate, validate, write.
"""

import argparse
import logging
import sys
import uuid
from pathlib import Path

from codegen.e2e_playwright import E2EPlaywrightGenerator
from codegen.node import NodeGenerator
from codegen.python import PythonGenerator
from codegen.react import ReactGenerator
from router import dispatcher
from schema import load_test_cases
from validators.report import validate_generated_files
from writer.output_writer import DEFAULT_OUTPUT_ROOT, write_output

DEFAULT_INPUT = Path("services/testing/data/test_cases.json")

logger = logging.getLogger(__name__)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Step C: LLM-based test code generation")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="path to test_cases.json")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_ROOT, help="output root directory")
    parser.add_argument("--run-id", type=str, default=None, help="run id (default: a generated uuid-based id)")
    parser.add_argument(
        "--contracts-dir", type=Path, default=None,
        help="override the contracts/design-to-implementation/ path used for tech-stack resolution",
    )
    parser.add_argument(
        "--chunks-dir", type=Path, default=None,
        help="override the services/testing/data/Chunks/ path used for tech-stack resolution "
             "(preferred over --contracts-dir's extracted-requirements doc when both resolve)",
    )
    return parser


def _register_generators() -> None:
    dispatcher.register_generator("python", PythonGenerator())
    dispatcher.register_generator("node", NodeGenerator())
    dispatcher.register_generator("express", NodeGenerator())
    dispatcher.register_generator("react", ReactGenerator())
    # Still a stub -- registered so e2e_flow cases fail with a specific
    # "Phase 6, not implemented yet" reason instead of dispatcher's generic
    # "no generator registered" error.
    dispatcher.register_generator("e2e", E2EPlaywrightGenerator())


def run(
    input_path: Path,
    output_root: Path,
    run_id: str,
    contracts_dir: Path | None = None,
    chunks_dir: Path | None = None,
) -> Path:
    """Runs the full Step C pipeline once. Returns the run's output directory."""
    _register_generators()

    dispatch_kwargs = {}
    if contracts_dir is not None:
        dispatch_kwargs["contracts_dir"] = contracts_dir
    if chunks_dir is not None:
        dispatch_kwargs["chunks_dir"] = chunks_dir
    generated_files, generation_errors = dispatcher.dispatch(str(input_path), **dispatch_kwargs)

    test_case_file = load_test_cases(str(input_path))
    passed, rejected, report = validate_generated_files(generated_files, test_case_file.test_cases)

    run_dir = write_output(
        run_id, passed, rejected, report, output_root=output_root, generation_errors=generation_errors
    )

    logger.info(
        "run %s: %d file(s) generated, %d passed, %d rejected, %d generation error(s) -> %s",
        run_id, len(generated_files), len(passed), len(rejected), len(generation_errors), run_dir,
    )
    return run_dir


def _default_run_id() -> str:
    return f"run-{uuid.uuid4().hex[:8]}"


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = build_arg_parser().parse_args(argv)

    run_id = args.run_id or _default_run_id()
    run(args.input, args.output, run_id, contracts_dir=args.contracts_dir, chunks_dir=args.chunks_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
