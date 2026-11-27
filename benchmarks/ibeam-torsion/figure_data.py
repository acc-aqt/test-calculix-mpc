"""The series the figures plot, taken from one mesh level's results. No rendering."""

from dataclasses import dataclass

import numpy as np

from benchmark_parameters import MeshLevel
from deck import QUARTER_SPAN_FLANGES, TOP_FLANGE_TIP_LINE, Deck
from frd import FrdResults
from runner import BenchmarkResult

X, Y, Z = 0, 1, 2
_SXX = 0


@dataclass(frozen=True)
class ConvergencePoint:
    element_length: float
    """Element length along x, L / length divisions."""
    node_count: int
    tip_twist_error: float
    """Signed % error of φ(L) against Vlasov."""
    warping_stress_error: float
    """Mean of the four signed flange-tip σ_w(L/4) errors, which agree by symmetry."""


@dataclass(frozen=True)
class FigureSeries:
    mesh_level: MeshLevel
    twist_x: np.ndarray
    twist_phi: np.ndarray
    """The report's twist φ(x) at each x station, root to tip."""
    top_flange_z: np.ndarray
    top_flange_sxx: np.ndarray
    """σ_xx of the top flange at x = L/4, the mean through the thickness at each z, ordered
    by z. At z = ±b/2 this is the report's flange-tip warping stress."""
    bottom_flange_z: np.ndarray
    bottom_flange_sxx: np.ndarray
    """As top_flange_*, for the bottom flange."""
    flange_tip_x: np.ndarray
    flange_tip_sxx: np.ndarray
    """σ_xx on the top flange-tip edge at z = −b/2, the mean through the thickness at each x
    station, root to tip."""
    convergence: ConvergencePoint


@dataclass(frozen=True)
class MeshLevelResults:
    """Everything the figures draw from one solved mesh level."""

    result: BenchmarkResult
    frd: FrdResults
    series: FigureSeries


def figure_series(result: BenchmarkResult, frd: FrdResults, deck: Deck) -> FigureSeries:
    twist_x, twist_phi = (np.array(column) for column in zip(*result.twist_curve, strict=True))
    top_name, bottom_name = QUARTER_SPAN_FLANGES
    top_z, top_sxx = _mean_sxx_by(frd, deck.node_sets[top_name], Z)
    bottom_z, bottom_sxx = _mean_sxx_by(frd, deck.node_sets[bottom_name], Z)
    tip_x, tip_sxx = _mean_sxx_by(frd, deck.node_sets[TOP_FLANGE_TIP_LINE], X)
    return FigureSeries(
        mesh_level=result.mesh_level,
        twist_x=twist_x,
        twist_phi=twist_phi,
        top_flange_z=top_z,
        top_flange_sxx=top_sxx,
        bottom_flange_z=bottom_z,
        bottom_flange_sxx=bottom_sxx,
        flange_tip_x=tip_x,
        flange_tip_sxx=tip_sxx,
        convergence=_convergence_point(result, twist_x[-1]),
    )


def _convergence_point(result: BenchmarkResult, length: float) -> ConvergencePoint:
    return ConvergencePoint(
        element_length=length / result.mesh_level.length_divisions,
        node_count=result.node_count,
        tip_twist_error=result.tip_twist_error,
        warping_stress_error=float(np.mean(result.warping_stress_errors)),
    )


def _mean_sxx_by(
    frd: FrdResults, nodes: tuple[int, ...], axis: int
) -> tuple[np.ndarray, np.ndarray]:
    """The distinct positions of the nodes on the axis and their mean σ_xx at each."""
    positions = np.array([frd.nodes[n][axis] for n in nodes])
    sxx = np.array([frd.nodal_results["STRESS"][n][_SXX] for n in nodes])
    unique, group = np.unique(positions, return_inverse=True)
    return unique, np.bincount(group, weights=sxx) / np.bincount(group)
