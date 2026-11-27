"""Run the benchmark at the selected mesh levels and write the markdown report.

Exit codes: 0 report written (the verdict is not evaluated yet), 2 ccx missing, failed or
didn't converge, or the zero-twist guard tripped (no report is written).
"""

import argparse
import shutil
import sys
from pathlib import Path

from benchmark_parameters import IPE200_TORSION, MESH_LEVELS
from report import VERDICT_TEXT, render_report
from runner import CcxError, ccx_version, find_ccx, run_benchmark

HERE = Path(__file__).resolve().parent
LEVELS_BY_NAME = {level.name: level for level in MESH_LEVELS}


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    ccx = _given_ccx(args.ccx) if args.ccx else find_ccx()
    if ccx is None or not ccx.is_file():
        print(
            f"ccx not found ({ccx or 'set CCX or use --ccx'}); no report written", file=sys.stderr
        )
        return 2

    try:
        version = ccx_version(ccx)
        results = []
        for name in args.levels:
            print(f"Running mesh level {name} ...", flush=True)
            results.append(run_benchmark(LEVELS_BY_NAME[name], IPE200_TORSION, args.work_dir, ccx))
    except CcxError as error:
        print(f"{error}\nStopped; no report written.", file=sys.stderr)
        return 2

    args.report.write_text(render_report(results, IPE200_TORSION, version))
    print(f"Report written to {args.report}\nVerdict: {VERDICT_TEXT}")
    return 0


def _given_ccx(given: str) -> Path:
    """The --ccx value as a path, or looked up on PATH when it isn't an existing file."""
    path = Path(given)
    if path.is_file():
        return path
    on_path = shutil.which(given)
    return Path(on_path) if on_path else path


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--levels",
        nargs="+",
        choices=list(LEVELS_BY_NAME),
        default=list(LEVELS_BY_NAME),
        help="mesh levels to run (default: all)",
    )
    parser.add_argument("--report", type=Path, default=HERE / "REPORT.md")
    parser.add_argument("--work-dir", type=Path, default=HERE / "work")
    parser.add_argument(
        "--ccx",
        help="ccx executable, a path or a name on PATH (default: $CCX, PATH, then the env's ccx)",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
