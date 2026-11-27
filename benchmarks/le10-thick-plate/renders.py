"""3D views of the LE10 plate: PyVista renders off-screen from the .frd, laid out with matplotlib
so titles and legends match the 2D figures."""

from collections.abc import Callable, Sequence
from pathlib import Path

import numpy as np
import pyvista as pv
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Polygon

from benchmark_parameters import BenchmarkParameters, Ellipse
from deck import LINE_EE, POINT_D
from figure_data import MeshLevelResults
from frd import FrdResults
from palette import BLUE, EDGES, GREEN, INK, ORANGE, SECONDARY_INK, STEEL

RENDER_SIZE = (2400, 1600)
SYMMETRY = BLUE
OUTER = ORANGE
PRESSURE = GREEN
SUBDIVISION = 2
EDGE_SAMPLES = 9
FROM_THE_HOLE = (-1.0, -1.2, 1.1)
"""View direction that shows the top face, both symmetry faces and the hole."""
FROM_OUTSIDE = (1.0, 1.1, 0.7)
"""View direction that shows the top face and the outer face."""

# VTK QUADRATIC_HEXAHEDRON: corners 0-7, then the midside nodes of these edges at 8-19.
_VTK_EDGES = (
    (0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7),
)  # fmt: skip
_MIDSIDE = {frozenset(edge): 8 + n for n, edge in enumerate(_VTK_EDGES)}

Draw = Callable[[pv.Plotter], None]


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


def mesh_figure(levels: Sequence[MeshLevelResults], params: BenchmarkParameters, path: Path) -> str:
    shown = [levels[0], levels[-1]] if len(levels) > 1 else [levels[0]]
    fig = Figure(figsize=(8, 2.7), layout="constrained")
    axes = fig.subplots(1, len(shown), squeeze=False)[0]
    for ax, level in zip(axes, shown, strict=True):
        grid = plate_grid(level.frd)

        def draw(plotter: pv.Plotter, grid: pv.UnstructuredGrid = grid) -> None:
            _add_surface(plotter, grid, STEEL)
            plotter.add_mesh(_edge_lines(grid), color=EDGES, line_width=4)
            _look(plotter, FROM_THE_HOLE)

        r = level.result
        _show(
            ax,
            _render(draw),
            f"{r.mesh_level.label}: {r.element_count:,} elements, {r.node_count:,} nodes",
        )
    fig.savefig(path)

    names = " and ".join(level.result.mesh_level.label for level in shown)
    return (
        f"The {names} meshes, counted as elements around the annulus × across it × through the "
        "thickness, seen from the hole side above the plate: the x = 0 face on the left, the "
        "hole face in the middle and the y = 0 face on the right. Each line across the annulus "
        "joins the inner and outer ellipse at one parametric angle θ, (a cos θ, b sin θ), "
        "with uniform spacing, so the elements grow from the hole to the outer edge and from "
        "D (θ = 0) towards A (θ = 90°). All elements are 20-node bricks whose midside nodes "
        "sit on the ellipses, so each edge around the annulus is drawn as the quadratic curve "
        "through its midside node; the midside nodes themselves are not drawn. Each level "
        "halves the element size of the one before in all three directions."
    )


def boundary_conditions_figure(
    levels: Sequence[MeshLevelResults], params: BenchmarkParameters, path: Path
) -> str:
    level = levels[0]
    grid = plate_grid(level.frd)
    faces = _classified_faces(grid, params)
    line_ee = np.array([level.frd.nodes[n] for n in level.deck.node_sets[LINE_EE]])
    (d,) = level.deck.node_sets[POINT_D]
    point_d = np.array(level.frd.nodes[d])

    def from_the_hole(plotter: pv.Plotter) -> None:
        _add_faces(plotter, faces)
        plotter.add_points(point_d, color=INK, point_size=70, render_points_as_spheres=True)
        _look(plotter, FROM_THE_HOLE)

    def from_outside(plotter: pv.Plotter) -> None:
        _add_faces(plotter, faces)
        plotter.add_mesh(
            pv.lines_from_points(line_ee), color=INK, line_width=14, render_lines_as_tubes=True
        )
        _look(plotter, FROM_OUTSIDE)

    fig = Figure(figsize=(8, 7.0), layout="constrained")
    grid_spec = fig.add_gridspec(2, 2, height_ratios=(1, 1.7))
    hole_view, outside_view = fig.add_subplot(grid_spec[0, 0]), fig.add_subplot(grid_spec[0, 1])
    plan = fig.add_subplot(grid_spec[1, :])
    _show(hole_view, _render(from_the_hole), "Seen from the hole side")
    _show(outside_view, _render(from_outside), "Seen from outside")
    _draw_plan(plan, params)
    fig.legend(
        handles=[
            Patch(color=SYMMETRY, label="symmetry faces y = 0 (u_y = 0) and x = 0 (u_x = 0)"),
            Patch(color=OUTER, label="outer face, u_x = u_y = 0"),
            Patch(color=PRESSURE, label=f"top face, pressure p = {params.pressure:g} MPa"),
            Patch(color=STEEL, label="hole face and bottom face, free"),
            Line2D([], [], color=INK, linewidth=3, label="line EE′, u_z = 0"),
            Line2D([], [], color=INK, marker="o", linestyle="none", label="point D"),
        ],
        loc="outside lower center",
        ncols=2,
    )
    fig.savefig(path)

    half = params.thickness / 2
    return (
        "The supports and load of NAFEMS LE10 on the quarter model "
        f"({level.result.mesh_level.name} mesh). The two symmetry faces (blue) are held normal "
        "to themselves: u_y = 0 on the y = 0 face and u_x = 0 on the x = 0 face. The outer "
        "elliptical face (orange) is held in its plane, u_x = u_y = 0, and the plate rests on "
        "line EE′, the outer face at mid-thickness (z = 0), where u_z = 0 on every corner and "
        f"midside node. A uniform pressure of {params.pressure:g} MPa pushes down on the top "
        f"face (green, z = +{half:g} mm). The hole face and the bottom face are free. Point D, "
        f"where σ_yy is measured, is ({params.inner.semi_axis_x:g}, 0, +{half:g}) mm: on the "
        "hole edge, on the x axis, on the loaded face. Top left: seen from the hole side above "
        "the plate. Top right: seen from outside, with line EE′. Bottom: the top face in plan, "
        "z up out of the page."
    )


def _draw_plan(ax, params: BenchmarkParameters) -> None:
    inner, outer = params.inner, params.outer
    theta = np.linspace(0.0, np.pi / 2, 181)
    inner_arc, outer_arc = _arc(inner, theta), _arc(outer, theta)
    ax.add_patch(
        Polygon(np.vstack([inner_arc, outer_arc[::-1]]), facecolor=PRESSURE, edgecolor="none")
    )
    ax.plot(*outer_arc.T, color=OUTER, linewidth=5, solid_capstyle="butt")
    ax.plot(*outer_arc.T, color=INK, linewidth=1.5, linestyle=(0, (4, 3)))
    ax.plot(*inner_arc.T, color=SECONDARY_INK, linewidth=1)
    ax.plot([inner.semi_axis_x, outer.semi_axis_x], [0, 0], color=SYMMETRY, linewidth=5)
    ax.plot([0, 0], [inner.semi_axis_y, outer.semi_axis_y], color=SYMMETRY, linewidth=5)
    ax.plot(inner.semi_axis_x, 0, "o", color=INK, markersize=8, clip_on=False, zorder=3)
    ax.plot(
        0,
        inner.semi_axis_y,
        "o",
        color=INK,
        markerfacecolor="white",
        markersize=8,
        clip_on=False,
        zorder=3,
    )

    text = {"color": INK}
    ax.annotate("D", (inner.semi_axis_x, 0), xytext=(-12, 8), textcoords="offset points", **text)
    ax.annotate("A", (0, inner.semi_axis_y), xytext=(8, -14), textcoords="offset points", **text)
    ax.text(
        (inner.semi_axis_x + outer.semi_axis_x) / 2,
        -120,
        "y = 0 face: u_y = 0",
        ha="center",
        va="top",
        **text,
    )
    ax.text(
        -120,
        (inner.semi_axis_y + outer.semi_axis_y) / 2,
        "x = 0 face: u_x = 0",
        ha="right",
        va="center",
        rotation=90,
        **text,
    )
    corner = _arc(outer, np.array([np.pi / 4]))[0]
    ax.annotate(
        "outer face: u_x = u_y = 0\nline EE′ (z = 0, dashed): u_z = 0",
        corner,
        xytext=(40, 30),
        textcoords="offset points",
        va="bottom",
        arrowprops={"arrowstyle": "-", "color": SECONDARY_INK, "linewidth": 0.8},
        **text,
    )
    middle = (_arc(inner, np.array([np.pi / 4]))[0] + corner) / 2
    ax.text(
        *middle,
        f"top face\np = {params.pressure:g} MPa",
        ha="center",
        va="center",
        **text,
    )
    ax.text(*(0.45 * _arc(inner, np.array([np.pi / 4]))[0]), "hole (free)", ha="center", **text)

    ax.set_aspect("equal")
    ax.set_xlim(-0.12 * outer.semi_axis_x, 1.4 * outer.semi_axis_x)
    ax.set_ylim(-0.12 * outer.semi_axis_y, 1.12 * outer.semi_axis_y)
    ax.set_xlabel("x (mm)")
    ax.set_ylabel("y (mm)")
    ax.grid(False)
    ax.set_title(f"Top face in plan (z = +{params.thickness / 2:g} mm)")


def _arc(ellipse: Ellipse, theta: np.ndarray) -> np.ndarray:
    return np.column_stack(
        [ellipse.semi_axis_x * np.cos(theta), ellipse.semi_axis_y * np.sin(theta)]
    )


def _classified_faces(
    grid: pv.UnstructuredGrid, params: BenchmarkParameters
) -> list[tuple[pv.PolyData, str]]:
    """The plate's surface split into the faces the supports and load act on, with colours."""
    surface = _surface(grid)
    x, y, z = surface.cell_centers().points.T
    tolerance = 1e-6 * params.outer.semi_axis_x
    outer = params.outer
    on_outer = (x / outer.semi_axis_x) ** 2 + (y / outer.semi_axis_y) ** 2 > 1 - 1e-3
    on_top = z > params.thickness / 2 - tolerance
    on_symmetry = (np.abs(x) < tolerance) | (np.abs(y) < tolerance)
    free = ~(on_outer | on_top | on_symmetry)
    groups = ((on_symmetry, SYMMETRY), (on_outer, OUTER), (on_top, PRESSURE), (free, STEEL))
    return [(surface.extract_cells(np.flatnonzero(mask)), color) for mask, color in groups]


def _add_faces(plotter: pv.Plotter, faces: list[tuple[pv.PolyData, str]]) -> None:
    for face, color in faces:
        _add_shaded(plotter, face, color)


def _render(draw: Draw) -> np.ndarray:
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


def _look(plotter: pv.Plotter, direction: tuple[float, float, float]) -> None:
    plotter.view_vector(direction, viewup=(0.0, 0.0, 1.0))


def _surface(grid: pv.UnstructuredGrid) -> pv.PolyData:
    return grid.extract_surface(algorithm=None, nonlinear_subdivision=SUBDIVISION)


def _add_surface(plotter: pv.Plotter, grid: pv.UnstructuredGrid, color: str) -> None:
    _add_shaded(plotter, _surface(grid), color)


def _add_shaded(plotter: pv.Plotter, surface: pv.PolyData, color: str) -> None:
    """A surface pushed slightly back in depth, so lines drawn on it are not hidden."""
    actor = plotter.add_mesh(
        surface, color=color, ambient=0.3, smooth_shading=True, split_sharp_edges=True
    )
    actor.mapper.SetResolveCoincidentTopologyToPolygonOffset()
    actor.mapper.SetRelativeCoincidentTopologyPolygonOffsetParameters(2, 2)


def _edge_lines(grid: pv.UnstructuredGrid) -> pv.PolyData:
    """Every element edge as the quadratic curve through its two corners and midside node."""
    points = grid.points
    curves = {}
    for cell in grid.cells_dict[pv.CellType.QUADRATIC_HEXAHEDRON]:
        for a, b in _VTK_EDGES:
            key = frozenset((cell[a], cell[b]))
            if key not in curves:
                middle = cell[_MIDSIDE[frozenset((a, b))]]
                curves[key] = _quadratic_curve(points[cell[a]], points[middle], points[cell[b]])
    vertices = np.vstack(list(curves.values()))
    segments = [
        [EDGE_SAMPLES, *range(n * EDGE_SAMPLES, (n + 1) * EDGE_SAMPLES)] for n in range(len(curves))
    ]
    return pv.PolyData(vertices, lines=np.hstack(segments))


def _quadratic_curve(start: np.ndarray, middle: np.ndarray, end: np.ndarray) -> np.ndarray:
    t = np.linspace(0.0, 1.0, EDGE_SAMPLES)[:, None]
    return start * (1 - t) * (1 - 2 * t) + middle * 4 * t * (1 - t) + end * t * (2 * t - 1)
