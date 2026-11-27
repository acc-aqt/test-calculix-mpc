"""Run the benchmark at the selected mesh levels and write the markdown report.

Exit codes: 0 PASS (or no verdict because the fine level wasn't run), 1 FAIL,
2 ccx missing, failed or didn't converge (no report is written).
"""

import argparse
import sys
from pathlib import Path

from benchmark_parameters import IPE200_CANTILEVER, MESH_LEVELS
from report import render_report, verdict
from runner import CcxError, ccx_version, find_ccx, run_benchmark

HERE = Path(__file__).resolve().parent
LEVELS_BY_NAME = {level.name: level for level in MESH_LEVELS}


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    ccx = Path(args.ccx) if args.ccx else find_ccx()
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
            results.append(
                run_benchmark(LEVELS_BY_NAME[name], IPE200_CANTILEVER, args.work_dir, ccx)
            )
    except CcxError as error:
        print(f"{error}\nStopped; no report written.", file=sys.stderr)
        return 2

    args.report.write_text(render_report(results, IPE200_CANTILEVER, version))
    outcome = verdict(results)
    print(f"Report written to {args.report}\nVerdict: {outcome or 'not evaluated'}")
    return 1 if outcome == "FAIL" else 0


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
    parser.add_argument("--ccx", help="ccx executable (default: $CCX, PATH, then the env's ccx)")
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
