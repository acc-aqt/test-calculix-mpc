"""3D view of the twisted solid I-beam (figure 5): PyVista renders off-screen from the .frd, laid
out with matplotlib so titles and colour bars match the 2D figures."""

from collections.abc import Callable, Sequence
from pathlib import Path

import numpy as np
import pyvista as pv
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize
from matplotlib.figure import Figure
from matplotlib.patches import Polygon

from analytical import analytical_solution
from benchmark_parameters import BenchmarkParameters
from figure_data import MeshLevelResults, X, Y, Z
from frd import FrdResults
from palette import INK, OUTLINE, SECONDARY_INK, STEEL

RENDER_SIZE = (2400, 1400)
STRESS_MAP = "RdBu_r"
SUBDIVISION = 2
ROOT_ZONE_LENGTH = 600.0

Draw = Callable[[pv.Plotter], None]


def beam_grid(frd: FrdResults) -> pv.UnstructuredGrid:
    """The solved mesh with point data u (displacement) and sigma_xx."""
    ids = sorted(frd.nodes)
    index = {node: n for n, node in enumerate(ids)}
    cells = [[index[node] for node in vtk_hexahedron(c)] for c in frd.elements.values()]
    grid = pv.UnstructuredGrid(
        {pv.CellType.QUADRATIC_HEXAHEDRON: np.array(cells)},
        np.array([frd.nodes[node] for node in ids]),
    )
    grid.point_data["u"] = np.array([frd.nodal_results["DISP"][node][:3] for node in ids])
    grid.point_data["sigma_xx"] = np.array([frd.nodal_results["STRESS"][node][0] for node in ids])
    return grid


def vtk_hexahedron(frd_nodes: tuple[int, ...]) -> tuple[int, ...]:
    """A 20-node hexahedron from .frd order to VTK's QUADRATIC_HEXAHEDRON (and the deck's) order.

    The .frd lists the midside nodes of the edges joining the two faces at 13-16 and those of
    the far face's edges at 17-20; VTK has them the other way round.
    """
    return frd_nodes[:12] + frd_nodes[16:20] + frd_nodes[12:16]


def stress_figure(
    levels: Sequence[MeshLevelResults], params: BenchmarkParameters, path: Path
) -> str:
    level = levels[-1]
    name = level.result.mesh_level.name
    grid = beam_grid(level.frd)
    deformed = grid.warp_by_vector("u", factor=1.0)
    root_stress = analytical_solution(params).root_warping_stress
    limit = 10 * np.ceil(root_stress / 10)
    clim = (-limit, limit)
    sxx = grid.point_data["sigma_xx"]
    beyond = float(grid.points[np.abs(sxx) > limit, X].max())
    near_root = _cells_where(deformed, lambda x: x < ROOT_ZONE_LENGTH)
    tip_twist = level.result.tip_twist

    def whole(plotter: pv.Plotter) -> None:
        _add_field(plotter, deformed, clim)
        plotter.view_vector((0.45, 0.55, 1.0), viewup=(0.0, 1.0, 0.0))

    def root(plotter: pv.Plotter) -> None:
        _add_field(plotter, near_root, clim)
        plotter.view_vector((0.9, 0.75, 1.0), viewup=(0.0, 1.0, 0.0))

    fig = Figure(figsize=(8, 8.2), layout="constrained")
    grid_spec = fig.add_gridspec(2, 2, height_ratios=(1, 1.3), width_ratios=(1.6, 1))
    whole_view = fig.add_subplot(grid_spec[0, :])
    root_view, tip_view = fig.add_subplot(grid_spec[1, 0]), fig.add_subplot(grid_spec[1, 1])
    _show(whole_view, _render(whole), f"σ_xx on the twisted beam, {name} mesh, true scale")
    for x, label, ha in ((0.0, "root face", "left"), (1.0, "tip face", "right")):
        whole_view.text(x, 0.0, label, transform=whole_view.transAxes, ha=ha, color=SECONDARY_INK)
    _show(root_view, _render(root), f"first {ROOT_ZONE_LENGTH:g} mm from the root face")
    _draw_tip_face(tip_view, level.frd, params, tip_twist)
    _colorbar(fig, [whole_view, root_view, tip_view], clim)
    fig.savefig(path)

    return (
        f"Nodal σ_xx on the {name} mesh, drawn on the deformed beam at true scale, with a "
        "diverging colour map centred on zero. Top: the whole beam, seen from above the +z "
        "side. The warping stress is largest at the root and fades along the length, with "
        "opposite signs on the two edges of each flange and on the two flanges. Bottom left: "
        f"the first {ROOT_ZONE_LENGTH:g} mm. On the top flange the far edge (z = −b/2) is in "
        "tension (red) and the near edge (z = +b/2) in compression (blue); on the bottom flange "
        "it is the other way round: the + − − + pattern. Bottom right: the tip face looking "
        "along +x (from the root end, z to the right), the FE tip-face nodes in their deformed "
        "position over the "
        f"undeformed section; the section turns by φ(L) = {tip_twist:.3f} rad "
        f"({np.degrees(tip_twist):.1f}°) about the x axis, the top flange towards +z. The colour "
        f"range is ±{limit:g} MPa, just above the thin-walled root warping stress "
        f"{root_stress:.1f} MPa; only nodes within {beyond:.0f} mm of the root face go beyond "
        f"it, up to ±{np.abs(sxx).max():.0f} MPa at the fixed face's edges."
    )


def _draw_tip_face(ax, frd: FrdResults, params: BenchmarkParameters, tip_twist: float) -> None:
    tolerance = 1e-6 * params.length
    ids = [n for n, xyz in frd.nodes.items() if abs(xyz[X] - params.length) <= tolerance]
    position = np.array([frd.nodes[n] for n in ids])
    moved = position + np.array([frd.nodal_results["DISP"][n][:3] for n in ids])
    ax.add_patch(Polygon(_section_outline(params), facecolor=STEEL, edgecolor=OUTLINE))
    ax.plot(moved[:, Z], moved[:, Y], ".", color=INK, markersize=1.5)
    ax.annotate(
        f"φ(L) = {tip_twist:.3f} rad",
        (moved[:, Z].max(), moved[np.argmax(moved[:, Z]), Y]),
        xytext=(0.98, 0.98),
        textcoords="axes fraction",
        ha="right",
        va="top",
        color=INK,
    )
    ax.text(0.0, 0.0, "grey: undeformed", transform=ax.transAxes, color=SECONDARY_INK)
    ax.set_aspect("equal")
    ax.autoscale_view()
    ax.set_axis_off()
    ax.set_title("tip face, looking along +x")


def _section_outline(params: BenchmarkParameters) -> np.ndarray:
    """The I-section as a (z, y) polygon."""
    s = params.section
    h, b, tw = s.height / 2, s.flange_width / 2, s.web_thickness / 2
    inner = h - s.flange_thickness
    right = [(b, h), (b, inner), (tw, inner), (tw, -inner), (b, -inner), (b, -h)]
    left = [(-z, y) for z, y in reversed(right)]
    return np.array(right + left)


def _render(draw: Draw, parallel: bool = False) -> np.ndarray:
    plotter = pv.Plotter(
        off_screen=True,
        window_size=list(RENDER_SIZE),
        theme=pv.themes.DocumentTheme(),
        lighting="three lights",
    )
    plotter.set_background("white")
    plotter.enable_anti_aliasing("ssaa")
    plotter.enable_depth_peeling()
    draw(plotter)
    if parallel:
        plotter.enable_parallel_projection()
    plotter.reset_camera()
    image = plotter.screenshot(return_img=True)
    plotter.close()
    return _trim(image)


def _trim(image: np.ndarray, margin: int = 12) -> np.ndarray:
    ink = np.any(image < 250, axis=2)
    rows, cols = np.flatnonzero(ink.any(axis=1)), np.flatnonzero(ink.any(axis=0))
    return image[
        max(rows[0] - margin, 0) : rows[-1] + margin + 1,
        max(cols[0] - margin, 0) : cols[-1] + margin + 1,
    ]


def _show(ax, image: np.ndarray, title: str) -> None:
    ax.imshow(image, interpolation="lanczos")
    ax.set_axis_off()
    ax.set_title(title)


def _colorbar(fig, ax, clim) -> None:
    mappable = ScalarMappable(norm=Normalize(*clim), cmap=STRESS_MAP)
    fig.colorbar(
        mappable,
        ax=ax,
        orientation="horizontal",
        label="σ_xx (MPa)",
        shrink=0.6,
        aspect=30,
        extend="both",
    )


def _surface(grid: pv.UnstructuredGrid) -> pv.PolyData:
    return grid.extract_surface(algorithm=None, nonlinear_subdivision=SUBDIVISION)


def _add_field(plotter: pv.Plotter, grid, clim) -> None:
    plotter.add_mesh(
        _surface(grid),
        scalars="sigma_xx",
        cmap=STRESS_MAP,
        clim=clim,
        ambient=0.5,
        diffuse=0.6,
        smooth_shading=True,
        split_sharp_edges=True,
        show_scalar_bar=False,
    )


def _cells_where(grid, keep) -> pv.UnstructuredGrid:
    """The cells whose undeformed centre x coordinate passes keep."""
    undeformed = grid.points - grid.point_data["u"]
    cells = grid.cells_dict[pv.CellType.QUADRATIC_HEXAHEDRON]
    centres = undeformed[cells[:, :8], X].mean(axis=1)
    return grid.extract_cells(np.flatnonzero(keep(centres)))
