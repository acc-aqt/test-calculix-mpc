"""The series the figures plot, taken from one mesh level's results. No rendering."""

from dataclasses import dataclass

import numpy as np

from benchmark_parameters import BenchmarkParameters, MeshLevel
from frd import FrdResults
from runner import BenchmarkResult

X, Y, Z = 0, 1, 2


@dataclass(frozen=True)
class ConvergencePoint:
    element_size: float
    """Circumferential arc length of one element on the outer surface, 2π·r_o / divisions."""
    node_count: int
    reference_node_deflection: float
    """Magnitude of the reference node's u_y, from the .dat."""
    deflection_error: float
    fitted_stress_errors: tuple[float, float]
    """Midspan stress fit errors at the (top, bottom) fibre."""
    single_node_stress_errors: tuple[float, float]
    """Single-node midspan stress errors at the (top, bottom) fibre."""
    root_peak_von_mises: float


@dataclass(frozen=True)
class FigureSeries:
    mesh_level: MeshLevel
    deflection_x: np.ndarray
    deflection_v: np.ndarray
    """Downward deflection −u_y averaged over all nodes of each node plane, ordered by x. At the
    tip this is the report's tip-face mean deflection."""
    circumference_y: np.ndarray
    circumference_sxx: np.ndarray
    """σ_xx of every outer-surface node at x = L/2 (the nodes of the midspan stress fit), ordered
    by y."""
    top_fibre_x: np.ndarray
    top_fibre_sxx: np.ndarray
    """σ_xx of the outer-surface nodes on the top fibre (y = r_o, z = 0), ordered by x. At
    x = L/2 this is the report's single-node top-fibre stress."""
    convergence: ConvergencePoint


@dataclass(frozen=True)
class MeshLevelResults:
    """Everything the figures draw from one solved mesh level."""

    result: BenchmarkResult
    frd: FrdResults
    series: FigureSeries


def figure_series(
    result: BenchmarkResult, frd: FrdResults, params: BenchmarkParameters
) -> FigureSeries:
    nodes = _Nodes(frd, tolerance=1e-6 * params.length)
    deflection_x, uy = nodes.plane_mean_along_x(nodes.everywhere(), "DISP", Y)
    circumference_y, circumference_sxx = nodes.along(
        Y,
        nodes.at(X, params.length / 2) & nodes.at_radius(params.section.outer_radius),
        "STRESS",
        X,
    )
    top_fibre_x, top_fibre_sxx = nodes.along(
        X, nodes.at(Y, params.section.outer_radius) & nodes.at(Z, 0.0), "STRESS", X
    )
    return FigureSeries(
        mesh_level=result.mesh_level,
        deflection_x=deflection_x,
        deflection_v=-uy,
        circumference_y=circumference_y,
        circumference_sxx=circumference_sxx,
        top_fibre_x=top_fibre_x,
        top_fibre_sxx=top_fibre_sxx,
        convergence=_convergence_point(result, params),
    )


def _convergence_point(result: BenchmarkResult, params: BenchmarkParameters) -> ConvergencePoint:
    circumference = 2 * np.pi * params.section.outer_radius
    return ConvergencePoint(
        element_size=circumference / result.mesh_level.circumferential_divisions,
        node_count=result.node_count,
        reference_node_deflection=abs(result.reference_node_uy),
        deflection_error=result.deflection_error,
        fitted_stress_errors=(result.midspan_top_stress_error, result.midspan_bottom_stress_error),
        single_node_stress_errors=(result.top_fibre_stress_error, result.bottom_fibre_stress_error),
        root_peak_von_mises=result.root_peak_von_mises,
    )


class _Nodes:
    def __init__(self, frd: FrdResults, tolerance: float):
        self._frd = frd
        self._ids = np.array(sorted(frd.nodes))
        self._coordinates = np.array([frd.nodes[n] for n in self._ids])
        self._tolerance = tolerance

    def everywhere(self) -> np.ndarray:
        return np.full(len(self._ids), True)

    def at(self, axis: int, value: float) -> np.ndarray:
        return np.abs(self._coordinates[:, axis] - value) <= self._tolerance

    def at_radius(self, radius: float) -> np.ndarray:
        r = np.hypot(self._coordinates[:, Y], self._coordinates[:, Z])
        return np.abs(r - radius) <= self._tolerance

    def along(
        self, axis: int, selected: np.ndarray, field: str, component: int
    ) -> tuple[np.ndarray, np.ndarray]:
        """Positions on the axis and one result component of the selected nodes, by position."""
        positions = self._coordinates[selected, axis]
        order = np.argsort(positions, kind="stable")
        values = self._frd.nodal_results[field]
        ids = self._ids[selected][order]
        return positions[order], np.array([values[n][component] for n in ids])

    def plane_mean_along_x(
        self, selected: np.ndarray, field: str, component: int
    ) -> tuple[np.ndarray, np.ndarray]:
        """Node planes in x and the mean result component of the selected nodes on each."""
        x, values = self.along(X, selected, field, component)
        _, plane_of = np.unique(np.round(x / self._tolerance), return_inverse=True)
        counts = np.bincount(plane_of)
        return (
            np.bincount(plane_of, weights=x) / counts,
            np.bincount(plane_of, weights=values) / counts,
        )
