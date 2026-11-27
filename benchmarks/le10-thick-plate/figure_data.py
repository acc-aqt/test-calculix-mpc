"""What the figures draw from one solved mesh level. No rendering."""

from dataclasses import dataclass

import numpy as np

from benchmark_parameters import BenchmarkParameters, MeshLevel
from deck import HOLE_EDGE, THICKNESS_LINE_AT_D, Deck
from frd import SYY, FrdResults
from runner import BenchmarkResult

X, Y, Z = 0, 1, 2


@dataclass(frozen=True)
class ConvergencePoint:
    mesh_level: MeshLevel
    node_count: int
    stress_yy_at_d: float
    """C3D20R nodal σ_yy(D), the report's value."""
    stress_yy_at_d_error: float
    """Signed % error against the published value."""
    full_integration_stress_yy_at_d: float
    """C3D20 nodal σ_yy(D), information only."""
    full_integration_stress_yy_at_d_error: float


@dataclass(frozen=True)
class FigureSeries:
    mesh_level: MeshLevel
    thickness_z: np.ndarray
    thickness_syy: np.ndarray
    """Nodal σ_yy through the thickness at x = a_i, y = 0, bottom face to D, ordered by z."""
    hole_edge_theta: np.ndarray
    """Parametric angle θ in degrees of the top-face hole edge nodes, (a_i cos θ, b_i sin θ),
    from D (0°) to A (90°)."""
    hole_edge_syy: np.ndarray
    hole_edge_uz: np.ndarray
    """Nodal displacement u_z in mm along the hole edge, from D to A."""
    convergence: ConvergencePoint


@dataclass(frozen=True)
class MeshLevelResults:
    result: BenchmarkResult
    deck: Deck
    frd: FrdResults
    series: FigureSeries


def figure_series(
    result: BenchmarkResult,
    params: BenchmarkParameters,
    deck: Deck,
    frd: FrdResults,
    full_integration: BenchmarkResult,
) -> FigureSeries:
    inner = params.inner
    hole_theta = {
        n: np.degrees(
            np.arctan2(frd.nodes[n][Y] / inner.semi_axis_y, frd.nodes[n][X] / inner.semi_axis_x)
        )
        for n in deck.node_sets[HOLE_EDGE]
    }
    hole_nodes = sorted(hole_theta, key=hole_theta.get)
    thickness_nodes = sorted(deck.node_sets[THICKNESS_LINE_AT_D], key=lambda n: frd.nodes[n][Z])
    return FigureSeries(
        mesh_level=result.mesh_level,
        thickness_z=np.array([frd.nodes[n][Z] for n in thickness_nodes]),
        thickness_syy=_stress_yy(frd, thickness_nodes),
        hole_edge_theta=np.array([hole_theta[n] for n in hole_nodes]),
        hole_edge_syy=_stress_yy(frd, hole_nodes),
        hole_edge_uz=np.array([frd.nodal_results["DISP"][n][Z] for n in hole_nodes]),
        convergence=ConvergencePoint(
            mesh_level=result.mesh_level,
            node_count=result.node_count,
            stress_yy_at_d=result.stress_yy_at_d,
            stress_yy_at_d_error=result.stress_yy_at_d_error,
            full_integration_stress_yy_at_d=full_integration.stress_yy_at_d,
            full_integration_stress_yy_at_d_error=full_integration.stress_yy_at_d_error,
        ),
    )


def _stress_yy(frd: FrdResults, nodes: list[int]) -> np.ndarray:
    return np.array([frd.nodal_results["STRESS"][n][SYY] for n in nodes])
