"""Benchmark runner: deck -> ccx -> .frd and .dat -> result record for one mesh level."""

import os
import re
import shutil
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from analytical import AnalyticalSolution, analytical_solution
from benchmark_parameters import BenchmarkParameters, MeshLevel
from dat import read_printed_displacements
from deck import (
    MIDSPAN_BOTTOM_FIBRE,
    MIDSPAN_OUTER_SURFACE,
    MIDSPAN_TOP_FIBRE,
    REFERENCE_NODE,
    ROOT_FACE,
    TIP_FACE,
    Deck,
    generate_deck,
)
from frd import FrdResults, read_frd

JOB_NAME = "tube"


class CcxError(RuntimeError):
    """ccx did not finish the job, so there are no results to trust."""


@dataclass(frozen=True)
class BenchmarkResult:
    mesh_level: MeshLevel
    element_count: int
    node_count: int
    reference_node_uy: float
    """Signed tip displacement in y at the reference node (negative under the -y load)."""
    tip_face_mean_uy: float
    midspan_top_fitted_sxx: float
    """+a·r_o from the least-squares fit σ_xx = a·y over the midspan outer-surface nodes."""
    midspan_bottom_fitted_sxx: float
    """−a·r_o from the same fit."""
    top_fibre_sxx: float
    """Signed nodal σ_xx at the midspan top-fibre node (y = r_o)."""
    bottom_fibre_sxx: float
    """Signed nodal σ_xx at the midspan bottom-fibre node (y = −r_o)."""
    root_peak_von_mises: float
    """Largest nodal von Mises stress on the root face. Information only: the fixed end disturbs
    it (St-Venant), so it never affects the verdict."""
    analytical: AnalyticalSolution

    @property
    def deflection_error(self) -> float:
        return _percent_error(abs(self.reference_node_uy), self.analytical.timoshenko_deflection)

    @property
    def thin_wall_deflection_error(self) -> float:
        target = self.analytical.thin_wall_timoshenko_deflection
        return _percent_error(abs(self.reference_node_uy), target)

    @property
    def euler_bernoulli_deflection_error(self) -> float:
        target = self.analytical.euler_bernoulli_deflection
        return _percent_error(abs(self.reference_node_uy), target)

    @property
    def midspan_top_stress_error(self) -> float:
        """Signed % error of the fitted stress against +midspan stress."""
        return _percent_error(self.midspan_top_fitted_sxx, self.analytical.midspan_stress)

    @property
    def midspan_bottom_stress_error(self) -> float:
        """Signed % error of the fitted stress against −midspan stress."""
        return _percent_error(self.midspan_bottom_fitted_sxx, -self.analytical.midspan_stress)

    @property
    def top_fibre_stress_error(self) -> float:
        """Signed % error against +midspan stress: the top fibre is in tension."""
        return _percent_error(self.top_fibre_sxx, self.analytical.midspan_stress)

    @property
    def bottom_fibre_stress_error(self) -> float:
        """Signed % error against −midspan stress: the bottom fibre is in compression."""
        return _percent_error(self.bottom_fibre_sxx, -self.analytical.midspan_stress)


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
    _, dat = result_files(level, work_dir)
    return benchmark_result(level, params, deck, read_frd(frd), dat)


def result_files(level: MeshLevel, work_dir: Path) -> tuple[Path, Path]:
    """The .frd and .dat a solved mesh level leaves in work_dir."""
    job = work_dir / level.name / JOB_NAME
    return job.with_suffix(".frd"), job.with_suffix(".dat")


def benchmark_result(
    level: MeshLevel, params: BenchmarkParameters, deck: Deck, frd: FrdResults, dat: Path
) -> BenchmarkResult:
    """The result record of a mesh level from its deck and the .frd and .dat ccx wrote."""
    displacements, stresses = frd.nodal_results["DISP"], frd.nodal_results["STRESS"]
    printed = read_printed_displacements(dat)[REFERENCE_NODE]
    (reference,) = deck.node_sets[REFERENCE_NODE]
    (top,) = deck.node_sets[MIDSPAN_TOP_FIBRE]
    (bottom,) = deck.node_sets[MIDSPAN_BOTTOM_FIBRE]
    outer_radius = params.section.outer_radius
    slope = _bending_stress_slope(frd, deck.node_sets[MIDSPAN_OUTER_SURFACE])
    return BenchmarkResult(
        mesh_level=level,
        element_count=deck.element_count,
        node_count=deck.node_count,
        reference_node_uy=printed[reference][1],
        tip_face_mean_uy=_mean(displacements[n][1] for n in deck.node_sets[TIP_FACE]),
        midspan_top_fitted_sxx=slope * outer_radius,
        midspan_bottom_fitted_sxx=-slope * outer_radius,
        top_fibre_sxx=stresses[top][0],
        bottom_fibre_sxx=stresses[bottom][0],
        root_peak_von_mises=max(von_mises(stresses[n]) for n in deck.node_sets[ROOT_FACE]),
        analytical=analytical_solution(params),
    )


def _bending_stress_slope(frd: FrdResults, nodes: tuple[int, ...]) -> float:
    """The slope a of the least-squares fit σ_xx = a·y through the origin over the nodes."""
    stresses = frd.nodal_results["STRESS"]
    ys = [frd.nodes[n][1] for n in nodes]
    sxx = [stresses[n][0] for n in nodes]
    return sum(y * s for y, s in zip(ys, sxx, strict=True)) / sum(y * y for y in ys)


def _percent_error(value: float, target: float) -> float:
    return (value - target) / target * 100


def _mean(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / len(values)


def von_mises(stress) -> float | np.ndarray:
    """Von Mises stress of one (sxx, syy, szz, sxy, syz, szx) record, or of each row of an
    (n, 6) array."""
    sxx, syy, szz, sxy, syz, szx = np.moveaxis(np.asarray(stress)[..., :6], -1, 0)
    normal = (sxx - syy) ** 2 + (syy - szz) ** 2 + (szz - sxx) ** 2
    return np.sqrt(normal / 2 + 3 * (sxy**2 + syz**2 + szx**2))
