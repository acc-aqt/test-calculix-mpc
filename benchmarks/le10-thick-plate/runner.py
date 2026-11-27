"""Benchmark runner: deck -> ccx -> .frd and .dat -> result record for one mesh level."""

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from benchmark_parameters import BenchmarkParameters, MeshLevel
from dat import read_printed_integration_points
from deck import POINT_D, Deck, generate_deck
from frd import SYY, FrdResults, read_frd
from reference import target_stress_at_d

JOB_NAME = "le10"
_DAT_SYY = 1
"""Position of σ_yy in a .dat stress record (sxx, syy, szz, sxy, sxz, syz)."""


class CcxError(RuntimeError):
    """ccx did not finish the job, so there are no results to trust."""


@dataclass(frozen=True)
class BenchmarkResult:
    mesh_level: MeshLevel
    element_count: int
    node_count: int
    stress_at_d: tuple[float, float, float, float, float, float]
    """ccx's nodal stress at D (sxx, syy, szz, sxy, syz, szx), extrapolated from the
    integration points and averaged over the elements that share D."""
    integration_point_at_d: tuple[float, float, float]
    """The integration point nearest D, (x, y, z) in mm."""
    integration_point_stress_yy_at_d: float
    """σ_yy at that integration point, information only."""

    @property
    def stress_yy_at_d(self) -> float:
        return self.stress_at_d[SYY]

    @property
    def stress_yy_at_d_error(self) -> float:
        """Signed % error against the published σ_yy(D), so a flipped sign gives about −200 %."""
        target = target_stress_at_d()
        return (self.stress_yy_at_d - target) / target * 100

    @property
    def von_mises_at_d(self) -> float:
        return float(von_mises(self.stress_at_d))


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
    return benchmark_result(level, deck, read_frd(frd), frd.with_suffix(".dat"))


def benchmark_result(level: MeshLevel, deck: Deck, frd: FrdResults, dat: Path) -> BenchmarkResult:
    """The result record of a mesh level from its deck and the .frd and .dat ccx wrote.

    Raises CcxError when the .frd has no stresses or the .dat no integration-point stresses.
    """
    if "STRESS" not in frd.nodal_results:
        raise CcxError("ccx wrote no STRESS block to the .frd")
    printed = read_printed_integration_points(dat) if dat.is_file() else {}
    if not {"stresses", "global coordinates"} <= printed.keys():
        raise CcxError(f"ccx printed no integration-point stresses at D to {dat}")
    (d,) = deck.node_sets[POINT_D]
    point_d = np.array(frd.nodes[d])
    coordinates = printed["global coordinates"]
    nearest = min(coordinates, key=lambda key: np.linalg.norm(coordinates[key] - point_d))
    return BenchmarkResult(
        mesh_level=level,
        element_count=deck.element_count,
        node_count=deck.node_count,
        stress_at_d=frd.nodal_results["STRESS"][d][:6],
        integration_point_at_d=coordinates[nearest],
        integration_point_stress_yy_at_d=printed["stresses"][nearest][_DAT_SYY],
    )


def von_mises(stress) -> float | np.ndarray:
    """Von Mises stress of one (sxx, syy, szz, sxy, syz, szx) record, or of each row of an
    (n, 6) array."""
    sxx, syy, szz, sxy, syz, szx = np.moveaxis(np.asarray(stress)[..., :6], -1, 0)
    normal = (sxx - syy) ** 2 + (syy - szz) ** 2 + (szz - sxx) ** 2
    return np.sqrt(normal / 2 + 3 * (sxy**2 + syz**2 + szx**2))
