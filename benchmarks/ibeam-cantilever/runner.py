"""Benchmark runner: deck -> ccx -> .frd -> result record for one mesh level."""

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from analytical import AnalyticalSolution, analytical_solution
from benchmark_parameters import BenchmarkParameters, MeshLevel
from dat import read_printed_displacements
from deck import REFERENCE_NODE, WEB_CENTRELINE_TIP_NODE, generate_deck
from frd import read_nodal_results

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
    analytical: AnalyticalSolution

    @property
    def deflection_error(self) -> float:
        """% error of the reference-node tip deflection against the Timoshenko deflection."""
        target = self.analytical.timoshenko_deflection
        return (abs(self.reference_node_uy) - target) / target * 100


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
    displacements = read_nodal_results(frd)["DISP"]
    printed = read_printed_displacements(frd.with_suffix(".dat"))[REFERENCE_NODE]
    (reference,) = deck.node_sets[REFERENCE_NODE]
    (web_tip,) = deck.node_sets[WEB_CENTRELINE_TIP_NODE]
    return BenchmarkResult(
        mesh_level=level,
        element_count=deck.element_count,
        node_count=deck.node_count,
        reference_node_uy=printed[reference][1],
        web_centreline_tip_uy=displacements[web_tip][1],
        analytical=analytical_solution(params),
    )
