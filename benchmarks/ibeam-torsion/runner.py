"""Benchmark runner: deck -> ccx -> .frd -> result record for one mesh level."""

import os
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from analytical import AnalyticalSolution, analytical_solution
from benchmark_parameters import BenchmarkParameters, MeshLevel
from deck import BOTTOM_FLANGE_CENTRE_LINE, TOP_FLANGE_CENTRE_LINE, Deck, generate_deck
from frd import FrdResults, read_frd

JOB_NAME = "ibeam"
ZERO_TWIST_FRACTION = 0.01
"""A tip twist below this fraction of the St-Venant tip twist means the torque never arrived."""


class CcxError(RuntimeError):
    """ccx did not finish the job, so there are no results to trust."""


class ZeroTwistError(CcxError):
    """ccx finished, but the beam did not twist: the torque was lost on the way in."""


@dataclass(frozen=True)
class BenchmarkResult:
    mesh_level: MeshLevel
    element_count: int
    node_count: int
    twist_curve: tuple[tuple[float, float], ...]
    """(x, φ) at each x station with flange mid-plane centre nodes, root to tip, where
    φ = (u_z,top − u_z,bottom) / h_m from the mean u_z of each flange's centre nodes."""
    analytical: AnalyticalSolution

    @property
    def tip_twist(self) -> float:
        """φ(L), the twist at the tip face."""
        return self.twist_curve[-1][1]

    @property
    def tip_twist_error(self) -> float:
        """Signed % error against the Vlasov φ(L)."""
        return _percent_error(self.tip_twist, self.analytical.tip_twist)

    @property
    def st_venant_tip_twist_error(self) -> float:
        """Signed % error against the pure St-Venant φ_SV(L), information only."""
        return _percent_error(self.tip_twist, self.analytical.st_venant_tip_twist)


def find_ccx() -> Path | None:
    """The ccx executable: $CCX if set, else ccx on PATH, else the running Python env's ccx.

    None when the chosen candidate doesn't exist.
    """
    if override := os.environ.get("CCX"):
        candidate = Path(override)
    elif on_path := shutil.which("ccx"):
        candidate = Path(on_path)
    else:
        candidate = Path(sys.prefix) / "bin" / "ccx"
    return candidate if candidate.is_file() else None


def ccx_version(ccx: Path) -> str:
    """The version line printed by `ccx -v`, e.g. "Version 2.24". ccx exits 201 here, so the
    exit code is ignored."""
    completed = _run([str(ccx), "-v"], cwd=None)
    match = re.search(r"Version \S+", completed.stdout)
    if match is None:
        raise CcxError(f"could not read the ccx version from `{ccx} -v`:\n{completed.stdout}")
    return match.group(0)


def run_ccx(deck_text: str, job_dir: Path, ccx: Path) -> Path:
    """Write the deck into job_dir, solve it and return the .frd path. Raises CcxError."""
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / f"{JOB_NAME}.inp").write_text(deck_text)
    completed = _run([str(ccx), "-i", JOB_NAME], cwd=job_dir)
    output = completed.stdout + completed.stderr
    frd = job_dir / f"{JOB_NAME}.frd"
    if completed.returncode != 0 or "Job finished" not in output or not frd.is_file():
        errors = [line for line in output.splitlines() if "ERROR" in line]
        detail = "\n".join(errors) or "\n".join(output.splitlines()[-20:])
        raise CcxError(f"ccx failed in {job_dir} (exit code {completed.returncode}):\n{detail}")
    return frd


def _run(command: list[str], cwd: Path | None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    except OSError as error:
        raise CcxError(f"could not run {command[0]}: {error}") from error


def run_benchmark(
    level: MeshLevel, params: BenchmarkParameters, work_dir: Path, ccx: Path
) -> BenchmarkResult:
    deck = generate_deck(params, level)
    frd = run_ccx(deck.text, work_dir / level.name, ccx)
    return benchmark_result(level, params, deck, read_frd(frd))


def result_files(level: MeshLevel, work_dir: Path) -> tuple[Path, Path]:
    """The .frd and .dat a solved mesh level leaves in work_dir."""
    job = work_dir / level.name / JOB_NAME
    return job.with_suffix(".frd"), job.with_suffix(".dat")


def benchmark_result(
    level: MeshLevel, params: BenchmarkParameters, deck: Deck, frd: FrdResults
) -> BenchmarkResult:
    """The result record of a mesh level from its deck and the .frd ccx wrote.

    Raises ZeroTwistError when the tip barely twisted, and CcxError when the .frd has no
    displacements.
    """
    if "DISP" not in frd.nodal_results:
        raise CcxError("ccx wrote no DISP block to the .frd")
    analytical = analytical_solution(params)
    result = BenchmarkResult(
        mesh_level=level,
        element_count=deck.element_count,
        node_count=deck.node_count,
        twist_curve=_twist_curve(frd, deck, analytical.flange_mid_plane_distance),
        analytical=analytical,
    )
    threshold = ZERO_TWIST_FRACTION * analytical.st_venant_tip_twist
    if abs(result.tip_twist) < threshold:
        raise ZeroTwistError(
            f"zero-twist guard: the tip twisted by {result.tip_twist:.3g} rad, below "
            f"{ZERO_TWIST_FRACTION:.0%} of the St-Venant tip twist ({threshold:.3g} rad), so "
            "the torque did not reach the beam"
        )
    return result


def _twist_curve(
    frd: FrdResults, deck: Deck, mid_plane_distance: float
) -> tuple[tuple[float, float], ...]:
    top = _mean_uz_by_x(frd, deck.node_sets[TOP_FLANGE_CENTRE_LINE])
    bottom = _mean_uz_by_x(frd, deck.node_sets[BOTTOM_FLANGE_CENTRE_LINE])
    stations = sorted(top.keys() & bottom.keys())
    return tuple((x, (top[x] - bottom[x]) / mid_plane_distance) for x in stations)


def _mean_uz_by_x(frd: FrdResults, nodes: tuple[int, ...]) -> dict[float, float]:
    displacements = frd.nodal_results["DISP"]
    by_x: dict[float, list[float]] = defaultdict(list)
    for n in nodes:
        by_x[frd.nodes[n][0]].append(displacements[n][2])
    return {x: sum(uz) / len(uz) for x, uz in by_x.items()}


def _percent_error(value: float, target: float) -> float:
    return (value - target) / target * 100
