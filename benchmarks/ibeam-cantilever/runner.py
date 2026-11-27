"""Benchmark runner: deck -> ccx -> .frd -> result record for one mesh level."""

import math
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from analytical import AnalyticalSolution, analytical_solution
from benchmark_parameters import BenchmarkParameters, MeshLevel
from dat import read_printed_displacements
from deck import (
    MIDSPAN_BOTTOM_FLANGE,
    MIDSPAN_TOP_FLANGE,
    REFERENCE_NODE,
    ROOT_FACE,
    WEB_CENTRELINE_TIP_NODE,
    generate_deck,
)
from frd import NodalValues, read_nodal_results

JOB_NAME = "ibeam"


class CcxError(RuntimeError):
    """ccx did not finish the job, so there are no results to trust."""


@dataclass(frozen=True)
class BenchmarkResult:
    mesh_level: MeshLevel
    element_count: int
    node_count: int
    reference_node_uy: float
    """Signed tip displacement in y at the reference node (negative under the -y load)."""
    web_centreline_tip_uy: float
    midspan_top_sxx_width_mean: float
    """Signed nodal sigma_xx on the top flange outer surface at x = L/2, averaged across the
    full flange width (the spec's Further Notes option, not only the web-centreline node)."""
    midspan_bottom_sxx_width_mean: float
    """As midspan_top_sxx_width_mean, on the bottom flange outer surface."""
    root_peak_von_mises: float
    """Largest nodal von Mises stress on the root face. Information only: the fixed end disturbs
    it (St-Venant), so it never affects the verdict."""
    analytical: AnalyticalSolution

    @property
    def deflection_error(self) -> float:
        """% error of the reference-node tip deflection against the Timoshenko deflection."""
        target = self.analytical.timoshenko_deflection
        return _percent_error(self.reference_node_uy, target)

    @property
    def euler_bernoulli_deflection_error(self) -> float:
        """% error of the reference-node tip deflection against the Euler-Bernoulli deflection."""
        return _percent_error(self.reference_node_uy, self.analytical.euler_bernoulli_deflection)

    @property
    def midspan_top_stress_error(self) -> float:
        """% error of |midspan_top_sxx_width_mean| against the analytical midspan stress."""
        return _percent_error(self.midspan_top_sxx_width_mean, self.analytical.midspan_stress)

    @property
    def midspan_bottom_stress_error(self) -> float:
        """% error of |midspan_bottom_sxx_width_mean| against the analytical midspan stress."""
        return _percent_error(self.midspan_bottom_sxx_width_mean, self.analytical.midspan_stress)


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
    completed = subprocess.run([str(ccx), "-v"], capture_output=True, text=True, check=False)
    match = re.search(r"Version \S+", completed.stdout)
    if match is None:
        raise CcxError(f"could not read the ccx version from `{ccx} -v`:\n{completed.stdout}")
    return match.group(0)


def run_ccx(deck_text: str, job_dir: Path, ccx: Path) -> Path:
    """Write the deck into job_dir, solve it and return the .frd path. Raises CcxError."""
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / f"{JOB_NAME}.inp").write_text(deck_text)
    completed = subprocess.run(
        [str(ccx), "-i", JOB_NAME], cwd=job_dir, capture_output=True, text=True, check=False
    )
    output = completed.stdout + completed.stderr
    frd = job_dir / f"{JOB_NAME}.frd"
    if completed.returncode != 0 or "Job finished" not in output or not frd.is_file():
        errors = [line for line in output.splitlines() if "ERROR" in line]
        detail = "\n".join(errors) or "\n".join(output.splitlines()[-20:])
        raise CcxError(f"ccx failed in {job_dir} (exit code {completed.returncode}):\n{detail}")
    return frd


def run_benchmark(
    level: MeshLevel, params: BenchmarkParameters, work_dir: Path, ccx: Path
) -> BenchmarkResult:
    deck = generate_deck(params, level)
    frd = run_ccx(deck.text, work_dir / level.name, ccx)
    results = read_nodal_results(frd)
    displacements, stresses = results["DISP"], results["STRESS"]
    printed = read_printed_displacements(frd.with_suffix(".dat"))[REFERENCE_NODE]
    (reference,) = deck.node_sets[REFERENCE_NODE]
    (web_tip,) = deck.node_sets[WEB_CENTRELINE_TIP_NODE]
    return BenchmarkResult(
        mesh_level=level,
        element_count=deck.element_count,
        node_count=deck.node_count,
        reference_node_uy=printed[reference][1],
        web_centreline_tip_uy=displacements[web_tip][1],
        midspan_top_sxx_width_mean=_mean_sxx(stresses, deck.node_sets[MIDSPAN_TOP_FLANGE]),
        midspan_bottom_sxx_width_mean=_mean_sxx(stresses, deck.node_sets[MIDSPAN_BOTTOM_FLANGE]),
        root_peak_von_mises=max(_von_mises(stresses[n]) for n in deck.node_sets[ROOT_FACE]),
        analytical=analytical_solution(params),
    )


def _percent_error(value: float, target: float) -> float:
    return (abs(value) - target) / target * 100


def _mean_sxx(stresses: NodalValues, nodes: tuple[int, ...]) -> float:
    return sum(stresses[n][0] for n in nodes) / len(nodes)


def _von_mises(stress: tuple[float, ...]) -> float:
    sxx, syy, szz, sxy, syz, szx = stress[:6]
    normal = (sxx - syy) ** 2 + (syy - szz) ** 2 + (szz - sxx) ** 2
    return math.sqrt(normal / 2 + 3 * (sxy**2 + syz**2 + szx**2))
