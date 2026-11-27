"""3D PyVista renders of the solid I-beam (figures 1-4), drawn off-screen from the .frd."""

import numpy as np
import pyvista as pv

from frd import FrdResults


def beam_grid(frd: FrdResults) -> pv.UnstructuredGrid:
    """The solved mesh with point data u (displacement), u_y, sigma_xx and von_mises."""
    ids = sorted(frd.nodes)
    index = {node: n for n, node in enumerate(ids)}
    cells = [[index[node] for node in vtk_hexahedron(c)] for c in frd.elements.values()]
    grid = pv.UnstructuredGrid(
        {pv.CellType.QUADRATIC_HEXAHEDRON: np.array(cells)},
        np.array([frd.nodes[node] for node in ids]),
    )
    u = np.array([frd.nodal_results["DISP"][node][:3] for node in ids])
    stress = np.array([frd.nodal_results["STRESS"][node][:6] for node in ids])
    grid.point_data["u"] = u
    grid.point_data["u_y"] = u[:, 1]
    grid.point_data["sigma_xx"] = stress[:, 0]
    grid.point_data["von_mises"] = _von_mises(stress)
    return grid


def vtk_hexahedron(frd_nodes: tuple[int, ...]) -> tuple[int, ...]:
    """A 20-node hexahedron from .frd order to VTK's QUADRATIC_HEXAHEDRON (and the deck's) order.

    The .frd lists the midside nodes of the edges joining the two faces at 13-16 and those of
    the far face's edges at 17-20; VTK has them the other way round.
    """
    return frd_nodes[:12] + frd_nodes[16:20] + frd_nodes[12:16]


def _von_mises(stress: np.ndarray) -> np.ndarray:
    sxx, syy, szz, sxy, syz, szx = stress.T
    normal = (sxx - syy) ** 2 + (syy - szz) ** 2 + (szz - sxx) ** 2
    return np.sqrt(normal / 2 + 3 * (sxy**2 + syz**2 + szx**2))
