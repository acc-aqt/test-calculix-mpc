"""3D views of the solid tube (figures 1-4): PyVista renders off-screen from the .frd, laid out
with matplotlib so titles, legends and colour bars match the 2D figures.

The elements are quadratic and their edges on the circumference are arcs, so surfaces are drawn
subdivided and element edges are drawn as the quadratic curves through their midside nodes.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pyvista as pv
from matplotlib.cm import ScalarMappable
from matplotlib.collections import LineCollection, PolyCollection
from matplotlib.colors import Normalize
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle

from analytical import bending_stress_at
from benchmark_parameters import BenchmarkParameters
from deck import (
    MIDSPAN_BOTTOM_FIBRE,
    MIDSPAN_OUTER_SURFACE,
    MIDSPAN_TOP_FIBRE,
    TIP_FACE,
    generate_deck,
)
from figure_data import MeshLevelResults, X, Y, Z
from frd import FrdResults
from palette import BLUE, EDGES, GREEN, ORANGE, OUTLINE, RED, SECONDARY_INK, STEEL, WALL
from runner import von_mises

TIP_DROP_FRACTION = 0.1
RENDER_SIZE = (2400, 1600)
LOAD = RED
COUPLING = ORANGE
FIBRE = BLUE
MIDSPAN = GREEN
STRESS_MAP = "RdBu_r"
DISPLACEMENT_MAP = "viridis"
VON_MISES_MAP = "magma_r"
SUBDIVISION = 3
EDGE_SAMPLES = 9

# VTK QUADRATIC_HEXAHEDRON: corners 0-7, then the midside nodes of these edges at 8-19.
_VTK_EDGES = (
    (0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7),
)  # fmt: skip
_VTK_FACES = ((0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7))
_MIDSIDE = {frozenset(edge): 8 + n for n, edge in enumerate(_VTK_EDGES)}

Draw = Callable[[pv.Plotter], None]


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
    grid.point_data["von_mises"] = von_mises(stress)
    return grid


def vtk_hexahedron(frd_nodes: tuple[int, ...]) -> tuple[int, ...]:
    """A 20-node hexahedron from .frd order to VTK's QUADRATIC_HEXAHEDRON (and the deck's) order.

    The .frd lists the midside nodes of the edges joining the two faces at 13-16 and those of
    the far face's edges at 17-20; VTK has them the other way round.
    """
    return frd_nodes[:12] + frd_nodes[16:20] + frd_nodes[12:16]


def model_figure(
    levels: Sequence[MeshLevelResults], params: BenchmarkParameters, path: Path
) -> str:
    level = levels[0]
    frd = level.frd
    sets = generate_deck(params, level.result.mesh_level).node_sets
    grid = beam_grid(frd)
    length, r_o = params.length, params.section.outer_radius
    diameter = 2 * r_o

    def points(*names: str) -> np.ndarray:
        return np.array([frd.nodes[n] for name in names for n in sets[name]])

    tip_face = points(TIP_FACE)
    midspan = points(MIDSPAN_OUTER_SURFACE)
    fibres = points(MIDSPAN_TOP_FIBRE, MIDSPAN_BOTTOM_FIBRE)
    reference = np.array([length, 0.0, 0.0])

    def support(plotter: pv.Plotter) -> None:
        plotter.add_mesh(_wall(params), color=WALL)

    def load(plotter: pv.Plotter) -> None:
        plotter.add_mesh(_load_arrow(reference, params), color=LOAD)

    def overview(plotter: pv.Plotter) -> None:
        _add_surface(plotter, grid)
        support(plotter)
        load(plotter)
        plotter.add_points(midspan, color=MIDSPAN, point_size=30, render_points_as_spheres=True)
        _look(plotter, (1.0, 0.9, 1.7))

    def root(plotter: pv.Plotter) -> None:
        _add_surface(plotter, _cells_where(grid, lambda x: x < 1.5 * diameter))
        support(plotter)
        _look(plotter, (1.0, 0.7, 1.3))

    def tip(plotter: pv.Plotter) -> None:
        _add_surface(plotter, _cells_where(grid, lambda x: x > length - 1.5 * diameter))
        spokes = pv.PolyData(np.vstack([reference, tip_face]))
        spokes.lines = np.hstack([[2, 0, n] for n in range(1, len(tip_face) + 1)])
        plotter.add_mesh(spokes, color=COUPLING, line_width=3)
        load(plotter)
        _look(plotter, (2.6, 0.7, 1.0))

    fig = Figure(figsize=(8, 10), layout="constrained")
    grid_spec = fig.add_gridspec(3, 2, height_ratios=(1, 1.4, 1.6))
    whole = fig.add_subplot(grid_spec[0, :])
    near_root, near_tip = fig.add_subplot(grid_spec[1, 0]), fig.add_subplot(grid_spec[1, 1])
    tip_view, midspan_view = fig.add_subplot(grid_spec[2, 0]), fig.add_subplot(grid_spec[2, 1])
    _show(whole, _render(overview), f"Solid tube, L = {length:g} mm")
    _show(near_root, _render(root), "Root face: u_x = u_y = u_z = 0")
    _show(near_tip, _render(tip), "Tip face: distributing coupling")

    tolerance = 1e-6 * length
    _draw_section(tip_view, _section_faces(frd, length, tolerance), linewidth=0.6)
    for z, y in tip_face[:, [Z, Y]]:
        tip_view.plot([0.0, z], [0.0, y], color=COUPLING, linewidth=0.6, zorder=2)
    tip_view.plot(
        0.0,
        0.0,
        "o",
        markersize=14,
        markerfacecolor="white",
        markeredgecolor=LOAD,
        markeredgewidth=2,
        zorder=3,
    )
    tip_view.annotate(
        "reference node at the\nsection centroid (extra\nnode, not in the mesh;\nno material here)",
        (0.0, 0.0),
        xytext=(-0.02, 0.5),
        textcoords="axes fraction",
        ha="right",
        va="center",
        color=LOAD,
        **_callout(shrink=8),
    )
    tip_view.set_title("Tip face, along the beam axis")

    _draw_section(midspan_view, _section_faces(frd, length / 2, tolerance), linewidth=0.6)
    midspan_view.plot(
        midspan[:, Z], midspan[:, Y], "o", markersize=5, color=MIDSPAN, zorder=3, clip_on=False
    )
    midspan_view.plot(
        fibres[:, Z], fibres[:, Y], "o", markersize=7, color=FIBRE, zorder=4, clip_on=False
    )
    for label, y, va in (
        ("top-fibre node, y = +r_o", r_o, "top"),
        ("bottom-fibre node, y = −r_o", -r_o, "bottom"),
    ):
        midspan_view.annotate(
            label,
            (0.0, y),
            xytext=(0.0, 0.55 * y),
            ha="center",
            va=va,
            color=FIBRE,
            **_callout(shrink=5),
        )
    midspan_view.set_title("Section at x = L/2")

    fig.legend(
        handles=[
            Patch(color=WALL, label="root face, fixed"),
            Line2D([], [], color=LOAD, linewidth=3, label=f"tip load P = {params.tip_load:g} N"),
            Line2D(
                [],
                [],
                color=LOAD,
                marker="o",
                markerfacecolor="white",
                markersize=8,
                ls="none",
                label="reference node",
            ),
            Line2D([], [], color=COUPLING, label="distributing coupling"),
            Line2D(
                [], [], color=MIDSPAN, marker="o", ls="none", label="midspan outer-surface nodes"
            ),
            Line2D([], [], color=FIBRE, marker="o", ls="none", label="top- and bottom-fibre nodes"),
        ],
        loc="outside lower center",
        ncols=3,
    )
    fig.savefig(path)

    return (
        f"The solid tube ({level.result.mesh_level.name} mesh), x along the beam, y up. "
        "The root face (x = 0, grey wall) is fixed in all three directions. The tip load "
        f"P = {params.tip_load:g} N acts in −y on the reference node at the section centroid, "
        "and the distributing coupling (orange) spreads it over every tip-face node without "
        "stiffening the face. Bottom left: the tip face seen along the beam axis. The reference "
        "node (red ring) is an extra node in the empty middle of the tube; it is not in the "
        "`.frd`, so it is drawn at its position in the deck. Bottom right: the section at "
        f"x = L/2 with the {len(midspan)} midspan outer-surface nodes (green, corner and "
        "midside), over which the midspan stress fit σ_xx = a·y is taken, and the top- and "
        "bottom-fibre nodes (blue), whose single-node σ_xx is reported next to the fit. The "
        "outer-surface nodes are also marked on the whole tube at the top."
    )


def meshes_figure(
    levels: Sequence[MeshLevelResults], params: BenchmarkParameters, path: Path
) -> str:
    s = params.section
    root_length = 2 * s.outer_radius
    half_width = 0.3 * s.outer_radius
    wall = _Window(z=(-half_width, half_width), y=(s.inner_radius - 6, s.outer_radius + 3))
    fig = Figure(figsize=(8, 2.7 * len(levels)), layout="constrained")
    axes = fig.subplots(len(levels), 3, squeeze=False, width_ratios=(2.4, 1.3, 1.3))
    for (isometric, section, close_up), level in zip(axes, levels, strict=True):
        grid = beam_grid(level.frd)
        near_root = _cells_where(grid, lambda x: x < root_length)

        def iso(plotter: pv.Plotter, mesh: pv.UnstructuredGrid = near_root) -> None:
            _add_surface(plotter, mesh)
            plotter.add_mesh(_edge_lines(mesh), color=EDGES, line_width=7)
            _look(plotter, (1.0, 0.8, 1.6))

        _show(
            isometric,
            _render(iso),
            f"{level.result.mesh_level.label}: {level.result.element_count:,} elements, "
            f"{level.result.node_count:,} nodes",
        )
        faces = _section_faces(level.frd, 0.0, tolerance=1e-6 * params.length)
        _draw_section(section, faces, linewidth=0.5)
        section.set_title("cross-section")
        wall.outline(section)
        _draw_section(close_up, faces, linewidth=1.0)
        wall.frame(close_up)
        close_up.set_title("blue box enlarged")
    fig.savefig(path)

    names = ", ".join(level.result.mesh_level.label for level in levels)
    return (
        "The mesh levels, labelled with the element counts around the circumference, through "
        f"the wall and along the length ({names}). Left: the first {root_length:g} mm of the "
        "tube from the root face. Middle: the whole cross-section on the root face, seen along "
        "the beam axis. Right: the blue box of the middle view enlarged, at the top fibre, "
        "showing the elements through the wall thickness. All elements are 20-node C3D20R "
        "bricks whose midside nodes sit on the true arcs, so each element edge around the "
        "circumference is drawn as the quadratic curve through its midside node; the midside "
        "nodes themselves are not drawn. Every level halves the element size of the one before "
        "in all three directions. As in REPORT.md and figure 8, the node counts include the "
        "reference node."
    )


def deformed_figure(
    levels: Sequence[MeshLevelResults], params: BenchmarkParameters, path: Path
) -> str:
    level = levels[-1]
    name = level.result.mesh_level.name
    grid = beam_grid(level.frd)
    uy = grid.point_data["u_y"]
    tip_drop = -uy.min()
    scale = round(TIP_DROP_FRACTION * params.length / tip_drop)
    deformed = grid.warp_by_vector("u", factor=scale)
    clim = (float(uy.min()), 0.0)

    def draw(plotter: pv.Plotter) -> None:
        plotter.add_mesh(_surface(grid), color=OUTLINE, opacity=0.25)
        _add_field(plotter, deformed, "u_y", DISPLACEMENT_MAP, clim)
        _look(plotter, (0.35, 0.3, 1.0))

    fig = Figure(figsize=(8, 3.6), layout="constrained")
    ax = fig.subplots()
    _show(ax, _render(draw), f"Deformed shape, {name} mesh, displacements × {scale}")
    _colorbar(fig, ax, DISPLACEMENT_MAP, clim, "u_y (mm)")
    ax.text(
        0.0,
        0.0,
        f"grey: undeformed\ndeformation scale × {scale}",
        transform=ax.transAxes,
        va="bottom",
        color=SECONDARY_INK,
    )
    fig.savefig(path)

    return (
        f"Deformed shape of the {name} mesh coloured by the vertical displacement u_y, with "
        f"displacements scaled × {scale} so that the tip drop ({tip_drop:.3f} mm, the largest "
        f"|u_y|) shows as about {TIP_DROP_FRACTION * 100:g} % of L. The grey ghost is the "
        "undeformed tube. u_y is zero at the fixed root face and grows towards the tip like "
        "the deflection curve of figure 5."
    )


def stress_figure(
    levels: Sequence[MeshLevelResults], params: BenchmarkParameters, path: Path
) -> str:
    level = levels[-1]
    name = level.result.mesh_level.name
    grid = beam_grid(level.frd)
    r_o = params.section.outer_radius
    root_bending = bending_stress_at(params, 0.0, r_o)
    limit = 10 * np.ceil(root_bending / 10)
    stress_clim = (-limit, limit)
    root_length = 2 * r_o
    near_root = _cells_where(grid, lambda x: x < root_length)
    von_mises = near_root.point_data["von_mises"]
    peak = float(von_mises.max())
    mises_clim = (0.0, peak)
    peaks = near_root.points[von_mises >= 0.999 * peak]
    peak_radius = float(np.hypot(peaks[0, Y], peaks[0, Z]))
    peak_surface = (
        "outer"
        if abs(peak_radius - r_o) < abs(peak_radius - params.section.inner_radius)
        else "inner"
    )
    sxx = grid.point_data["sigma_xx"]
    beyond = float(grid.points[np.abs(sxx) > limit, X].max())

    def from_above(plotter: pv.Plotter) -> None:
        _add_field(plotter, grid, "sigma_xx", STRESS_MAP, stress_clim)
        plotter.view_vector((0.1, 1.0, 0.4), viewup=(0.0, 0.0, -1.0))

    def from_below(plotter: pv.Plotter) -> None:
        _add_field(plotter, grid, "sigma_xx", STRESS_MAP, stress_clim)
        plotter.view_vector((0.1, -1.0, -0.4), viewup=(0.0, 0.0, 1.0))

    def root(plotter: pv.Plotter) -> None:
        _add_field(plotter, near_root, "von_mises", VON_MISES_MAP, mises_clim)
        for corner in peaks:
            plotter.add_mesh(pv.Sphere(radius=2.5, center=corner), color=FIBRE)
        _look(plotter, (-1.5, 0.6, 0.8))

    fig = Figure(figsize=(8, 7.4), layout="constrained")
    grid_spec = fig.add_gridspec(3, 1, height_ratios=(1, 1, 2))
    above, below, mises = (fig.add_subplot(grid_spec[row]) for row in range(3))
    _show(
        above,
        _render(from_above, parallel=True),
        f"σ_xx, {name} mesh, from above: top in tension",
    )
    _show(below, _render(from_below, parallel=True), "from below: bottom in compression")
    for ax in (above, below):
        for x, label, ha in ((0.0, "root", "left"), (1.0, "tip", "right")):
            ax.text(x, -0.08, label, transform=ax.transAxes, ha=ha, va="top", color=SECONDARY_INK)
    _colorbar(fig, [above, below], STRESS_MAP, stress_clim, "σ_xx (MPa)", "vertical", extend="both")
    _show(mises, _render(root), "von Mises near the root, looking at the root face")
    _colorbar(fig, mises, VON_MISES_MAP, mises_clim, "von Mises (MPa)", "vertical")
    mises.text(
        0.0,
        0.5,
        f"blue dots: peak {peak:.0f} MPa\non the {peak_surface} surface\nat the root face",
        transform=mises.transAxes,
        ha="right",
        color=FIBRE,
    )
    fig.savefig(path)

    return (
        f"σ_xx on the {name} mesh, seen from above and from below, with a diverging colour "
        "map centred on zero. The hogging moment puts the top of the tube in tension (red) and "
        "the bottom in compression (blue), largest at the root and falling linearly to zero at "
        "the tip, with σ_xx changing sign across the neutral axis at the sides. The colour "
        f"range is ±{limit:g} MPa, just above the beam-theory root bending stress "
        f"P·L·r_o/I = {root_bending:.1f} MPa. Only nodes within {beyond:.0f} mm of the root "
        f"face go beyond it, up to ±{np.abs(sxx).max():.0f} MPa. Bottom: von Mises stress in "
        f"the first {root_length:g} mm, looking at the root face. The peak of {peak:.0f} MPa "
        f"(blue dots) is on the {peak_surface} surface where it meets the fixed root face. "
        "That is the disturbance of the fixed end, which grows from the coarse to the fine "
        "mesh level (figure 8), so the root stress is information only."
    )


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


def _colorbar(fig, ax, cmap, clim, label, orientation="horizontal", **options) -> None:
    mappable = ScalarMappable(norm=Normalize(*clim), cmap=cmap)
    fig.colorbar(
        mappable, ax=ax, orientation=orientation, label=label, shrink=0.6, aspect=30, **options
    )


def _look(plotter: pv.Plotter, direction: tuple[float, float, float]) -> None:
    plotter.view_vector(direction, viewup=(0.0, 1.0, 0.0))


def _surface(grid: pv.UnstructuredGrid) -> pv.PolyData:
    return grid.extract_surface(algorithm=None, nonlinear_subdivision=SUBDIVISION)


def _add_surface(plotter: pv.Plotter, grid: pv.UnstructuredGrid) -> None:
    plotter.add_mesh(
        _surface(grid), color=STEEL, ambient=0.25, smooth_shading=True, split_sharp_edges=True
    )


def _add_field(plotter: pv.Plotter, grid, scalars: str, cmap: str, clim) -> None:
    plotter.add_mesh(
        _surface(grid),
        scalars=scalars,
        cmap=cmap,
        clim=clim,
        ambient=0.5,
        diffuse=0.6,
        smooth_shading=True,
        split_sharp_edges=True,
        show_scalar_bar=False,
    )


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


def _wall(params: BenchmarkParameters) -> pv.PolyData:
    d = 2 * params.section.outer_radius
    return pv.Box((-0.15 * d, 0.0, -0.75 * d, 0.75 * d, -0.75 * d, 0.75 * d))


def _load_arrow(reference: np.ndarray, params: BenchmarkParameters) -> pv.PolyData:
    d = 2 * params.section.outer_radius
    length = 1.3 * d
    gap = 0.55 * d
    return pv.Arrow(
        start=reference + [0.0, length + gap, 0.0],
        direction=(0.0, -1.0, 0.0),
        scale=length,
        tip_length=0.15,
        tip_radius=0.04,
        shaft_radius=0.012,
    )


def _cells_where(grid: pv.UnstructuredGrid, keep, axis: int = X) -> pv.UnstructuredGrid:
    """The cells whose centre coordinate on the axis (default x) passes keep."""
    centres = grid.cell_centers().points[:, axis]
    return grid.extract_cells(np.flatnonzero(keep(centres)))


def _callout(shrink: float) -> dict:
    return {
        "arrowprops": {
            "arrowstyle": "-",
            "color": SECONDARY_INK,
            "linewidth": 0.8,
            "shrinkB": shrink,
        }
    }


def _section_faces(frd: FrdResults, x: float, tolerance: float) -> list[np.ndarray]:
    """The element faces on the plane x as (z, y) outlines, seen along the beam axis, with each
    edge drawn as the quadratic curve through its midside node."""
    faces = {}
    for element in frd.elements.values():
        cell = vtk_hexahedron(element)
        for face in _VTK_FACES:
            corners = [cell[n] for n in face]
            if all(abs(frd.nodes[n][X] - x) <= tolerance for n in corners):
                faces.setdefault(frozenset(corners), (cell, face))
    outlines = []
    for cell, face in faces.values():
        edges = []
        for a, b in zip(face, face[1:] + face[:1], strict=True):
            start, middle, end = (
                np.array(frd.nodes[n])[[Z, Y]]
                for n in (cell[a], cell[_MIDSIDE[frozenset((a, b))]], cell[b])
            )
            edges.append(_quadratic_curve(start, middle, end)[:-1])
        outlines.append(np.vstack(edges))
    return outlines


def _draw_section(ax, faces: list[np.ndarray], linewidth: float) -> None:
    ax.add_collection(PolyCollection(faces, facecolor=STEEL, edgecolor="none"))
    ax.add_collection(
        LineCollection([np.vstack([f, f[:1]]) for f in faces], color=EDGES, linewidth=linewidth)
    )
    ax.autoscale_view()
    ax.set_aspect("equal")
    ax.set_axis_off()


@dataclass(frozen=True)
class _Window:
    """A (z, y) region of a cross-section view."""

    z: tuple[float, float]
    y: tuple[float, float]

    def outline(self, ax) -> None:
        ax.add_patch(
            Rectangle(
                (self.z[0], self.y[0]),
                self.z[1] - self.z[0],
                self.y[1] - self.y[0],
                fill=False,
                edgecolor=BLUE,
                linewidth=1,
            )
        )

    def frame(self, ax) -> None:
        ax.set_xlim(*self.z)
        ax.set_ylim(*self.y)
        ax.set_axis_on()
        ax.set_xticks([])
        ax.set_yticks([])
        ax.grid(False)
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_edgecolor(BLUE)
