"""The series the figures plot, taken from one mesh level's results. No rendering."""

from dataclasses import dataclass

import numpy as np

from benchmark_parameters import BenchmarkParameters, MeshLevel
from frd import FrdResults
from runner import BenchmarkResult

X, Y, Z = 0, 1, 2


@dataclass(frozen=True)
class ConvergencePoint:
    node_count: int
    reference_node_deflection: float
    """Magnitude of the reference node's u_y, from the .dat."""
    deflection_error: float
    top_stress_error: float
    bottom_stress_error: float
    root_peak_von_mises: float


@dataclass(frozen=True)
class FigureSeries:
    mesh_level: MeshLevel
    deflection_x: np.ndarray
    deflection_v: np.ndarray
    """Downward deflection −u_y on the web centreline (y = z = 0), ordered by x."""
    depth_y: np.ndarray
    depth_sxx: np.ndarray
    """σ_xx through the depth at x = L/2 on the mid-plane z = 0, ordered by y."""
    top_flange_x: np.ndarray
    top_flange_sxx: np.ndarray
    """σ_xx on the top flange outer surface (y = h/2), averaged across the flange width at each
    node plane, ordered by x. At x = L/2 this is the report's midspan top-flange stress."""
    convergence: ConvergencePoint


def figure_series(
    result: BenchmarkResult, frd: FrdResults, params: BenchmarkParameters
) -> FigureSeries:
    nodes = _Nodes(frd, tolerance=1e-6 * params.length)
    deflection_x, uy = nodes.along(X, nodes.at(Y, 0.0) & nodes.at(Z, 0.0), "DISP", Y)
    depth_y, depth_sxx = nodes.along(
        Y, nodes.at(X, params.length / 2) & nodes.at(Z, 0.0), "STRESS", X
    )
    top_flange_x, top_flange_sxx = nodes.width_mean_along_x(
        nodes.at(Y, params.section.height / 2), "STRESS", X
    )
    return FigureSeries(
        mesh_level=result.mesh_level,
        deflection_x=deflection_x,
        deflection_v=-uy,
        depth_y=depth_y,
        depth_sxx=depth_sxx,
        top_flange_x=top_flange_x,
        top_flange_sxx=top_flange_sxx,
        convergence=ConvergencePoint(
            node_count=result.node_count,
            reference_node_deflection=abs(result.reference_node_uy),
            deflection_error=result.deflection_error,
            top_stress_error=result.midspan_top_stress_error,
            bottom_stress_error=result.midspan_bottom_stress_error,
            root_peak_von_mises=result.root_peak_von_mises,
        ),
    )


class _Nodes:
    def __init__(self, frd: FrdResults, tolerance: float):
        self._frd = frd
        self._ids = np.array(sorted(frd.nodes))
        self._coordinates = np.array([frd.nodes[n] for n in self._ids])
        self._tolerance = tolerance

    def at(self, axis: int, value: float) -> np.ndarray:
        return np.abs(self._coordinates[:, axis] - value) <= self._tolerance

    def along(
        self, axis: int, selected: np.ndarray, field: str, component: int
    ) -> tuple[np.ndarray, np.ndarray]:
        """Positions on the axis and one result component of the selected nodes, by position."""
        positions = self._coordinates[selected, axis]
        order = np.argsort(positions)
        values = self._frd.nodal_results[field]
        ids = self._ids[selected][order]
        return positions[order], np.array([values[n][component] for n in ids])

    def width_mean_along_x(
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
