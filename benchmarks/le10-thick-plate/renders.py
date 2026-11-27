"""3D views of the LE10 plate: PyVista renders off-screen from the .frd, laid out with matplotlib
so titles and legends match the 2D figures."""

import numpy as np
import pyvista as pv

from frd import FrdResults


def plate_grid(frd: FrdResults) -> pv.UnstructuredGrid:
    """The solved mesh as 20-node hexahedra."""
    ids = sorted(frd.nodes)
    index = {node: n for n, node in enumerate(ids)}
    cells = [[index[node] for node in vtk_hexahedron(c)] for c in frd.elements.values()]
    return pv.UnstructuredGrid(
        {pv.CellType.QUADRATIC_HEXAHEDRON: np.array(cells)},
        np.array([frd.nodes[node] for node in ids]),
    )


def vtk_hexahedron(frd_nodes: tuple[int, ...]) -> tuple[int, ...]:
    """A 20-node hexahedron from .frd order to VTK's QUADRATIC_HEXAHEDRON (and the deck's) order.

    The .frd lists the midside nodes of the edges joining the two faces at 13-16 and those of
    the far face's edges at 17-20; VTK has them the other way round.
    """
    return frd_nodes[:12] + frd_nodes[16:20] + frd_nodes[12:16]
