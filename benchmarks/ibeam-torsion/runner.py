"""Benchmark runner: deck -> ccx -> .frd -> result record for one mesh level."""

import os
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from analytical import AnalyticalSolution, analytical_solution, warping_stress_at
from benchmark_parameters import BenchmarkParameters, MeshLevel
from deck import (
    BOTTOM_FLANGE_MID_PLANE_CENTRE_NODES,
    FLANGE_TIP_EDGES,
    MIDSPAN_FLANGE_SURFACES,
    ROOT_FACE,
    TOP_FLANGE_MID_PLANE_CENTRE_NODES,
    TOP_FLANGE_TIP_LINE,
    Deck,
    generate_deck,
)
from frd import SXX, SZX, FrdResults, NodalValues, read_frd

JOB_NAME = "ibeam"
ZERO_TWIST_FRACTION = 0.01
"""A tip twist below this fraction of the St-Venant tip twist means the torque never arrived."""
_UZ = 2
"""Position of u_z in a .frd DISP record."""


class CcxError(RuntimeError):
    """ccx did not finish the job, so there are no results to trust."""


class ZeroTwistError(RuntimeError):
    """ccx finished, but the beam did not twist: the torque was lost on the way in."""


@dataclass(frozen=True)
class BenchmarkResult:
    mesh_level: MeshLevel
    element_count: int
    node_count: int
    twist_curve: tuple[tuple[float, float], ...]
    """(x, φ) at each x station with flange mid-plane centre nodes, root to tip, where
    φ = (u_z,top − u_z,bottom) / h_m from the mean u_z of each flange's centre nodes."""
    flange_tip_warping_stresses: tuple[float, float, float, float]
    """Signed mean nodal σ_xx over each flange-tip edge at x = L/4, through the flange thickness:
    top flange at z = −b/2 and +b/2, then bottom flange at z = −b/2 and +b/2."""
    flange_tip_stress_curve: tuple[tuple[float, float], ...]
    """(x, σ_xx) along the top flange-tip edge at z = −b/2, the mean nodal σ_xx through the
    flange thickness at each x station, root to tip."""
    midspan_st_venant_shear_stress: float
    """Mean nodal τ_xz on the top flange outer surface minus that on the bottom one, halved, at
    the outstand centres at x = L/2. Information only: warping shear is mixed in."""
    root_peak_von_mises: float
    """Largest nodal von Mises stress on the root face. Information only: the fixed face is
    singular where it meets the free surfaces."""
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

    @property
    def warping_stress_errors(self) -> tuple[float, ...]:
        """Signed % errors against the signed σ_w(L/4) at each flange tip, so a flipped sign
        gives about −200 %."""
        targets = self.analytical.quarter_span_flange_tip_warping_stresses
        return tuple(
            _percent_error(value, target)
            for value, target in zip(self.flange_tip_warping_stresses, targets, strict=True)
        )

    @property
    def st_venant_shear_stress_error(self) -> float:
        """Signed % error against G·t_f·φ'(L/2), information only."""
        return _percent_error(
            self.midspan_st_venant_shear_stress, self.analytical.midspan_st_venant_shear_stress
        )


@dataclass(frozen=True)
class TipZone:
    """How the tip load-introduction zone shows on the top flange-tip σ_xx of one mesh level."""

    onset_x: float
    """The first x station past L/4 where σ_xx is more than ONSET_MARGIN above the Vlasov
    curve with the end-corrected J, or L when there is none before the tip."""
    plateau_min: float
    plateau_max: float
    """The range of σ_xx over PLATEAU_RANGE, where Vlasov has fallen to a few MPa."""
    quarter_span_vs_end_corrected: float
    """Signed % difference of σ_xx at x = L/4 from the end-corrected Vlasov curve."""


PLATEAU_RANGE = (2000.0, 2800.0)
"""The x range (mm) over which the flange-tip σ_xx levels off in the tip zone."""
ONSET_MARGIN = 0.02


def tip_zone(result: BenchmarkResult, params: BenchmarkParameters) -> TipZone:
    """The tip-zone numbers of the report and of figure 3, from the flange-tip σ_xx curve."""
    x, sxx = (np.array(column) for column in zip(*result.flange_tip_stress_curve, strict=True))
    length = params.length
    a = result.analytical
    corrected = warping_stress_at(
        params,
        x,
        a.flange_mid_plane_distance / 2,
        -params.section.flange_width / 2,
        a.end_corrected_torsion_constant,
    )
    beyond_quarter = (x > length / 4) & (x < length)
    above = beyond_quarter & (sxx > (1 + ONSET_MARGIN) * corrected)
    plateau = sxx[(x >= PLATEAU_RANGE[0]) & (x <= PLATEAU_RANGE[1])]
    quarter = np.isclose(x, length / 4)
    return TipZone(
        onset_x=float(x[above].min()) if above.any() else float(length),
        plateau_min=float(plateau.min()),
        plateau_max=float(plateau.max()),
        quarter_span_vs_end_corrected=float((sxx[quarter][0] / corrected[quarter][0] - 1) * 100),
    )


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
    for block in ("DISP", "STRESS"):
        if block not in frd.nodal_results:
            raise CcxError(f"ccx wrote no {block} block to the .frd")
    analytical = analytical_solution(params)
    stresses = frd.nodal_results["STRESS"]
    top_surface, bottom_surface = (deck.node_sets[name] for name in MIDSPAN_FLANGE_SURFACES)
    result = BenchmarkResult(
        mesh_level=level,
        element_count=deck.element_count,
        node_count=deck.node_count,
        twist_curve=_twist_curve(frd, deck, analytical.flange_mid_plane_distance),
        flange_tip_warping_stresses=tuple(
            _mean_component(stresses, deck.node_sets[name], SXX) for name in FLANGE_TIP_EDGES
        ),
        flange_tip_stress_curve=tuple(
            sorted(_mean_by_x(frd, deck.node_sets[TOP_FLANGE_TIP_LINE], "STRESS", SXX).items())
        ),
        midspan_st_venant_shear_stress=(
            _mean_component(stresses, top_surface, SZX)
            - _mean_component(stresses, bottom_surface, SZX)
        )
        / 2,
        root_peak_von_mises=float(max(von_mises(stresses[n]) for n in deck.node_sets[ROOT_FACE])),
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
    top = _mean_by_x(frd, deck.node_sets[TOP_FLANGE_MID_PLANE_CENTRE_NODES], "DISP", _UZ)
    bottom = _mean_by_x(frd, deck.node_sets[BOTTOM_FLANGE_MID_PLANE_CENTRE_NODES], "DISP", _UZ)
    stations = sorted(top.keys() & bottom.keys())
    return tuple((x, (top[x] - bottom[x]) / mid_plane_distance) for x in stations)


def _mean_by_x(
    frd: FrdResults, nodes: tuple[int, ...], block: str, component: int
) -> dict[float, float]:
    """The mean of one component of a .frd result block over the nodes at each x station."""
    values = frd.nodal_results[block]
    by_x: dict[float, list[float]] = defaultdict(list)
    for n in nodes:
        by_x[frd.nodes[n][0]].append(values[n][component])
    return {x: sum(v) / len(v) for x, v in by_x.items()}


def _mean_component(stresses: NodalValues, nodes: tuple[int, ...], component: int) -> float:
    return sum(stresses[n][component] for n in nodes) / len(nodes)


def von_mises(stress) -> float | np.ndarray:
    """Von Mises stress of one (sxx, syy, szz, sxy, syz, szx) record, or of each row of an
    (n, 6) array."""
    sxx, syy, szz, sxy, syz, szx = np.moveaxis(np.asarray(stress)[..., :6], -1, 0)
    normal = (sxx - syy) ** 2 + (syy - szz) ** 2 + (szz - sxx) ** 2
    return np.sqrt(normal / 2 + 3 * (sxy**2 + syz**2 + szx**2))


def _percent_error(value: float, target: float) -> float:
    return (value - target) / target * 100
