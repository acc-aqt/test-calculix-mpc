"""3D views of the solid I-beam (figures 1-4): PyVista renders off-screen from the .frd, laid
out with matplotlib so titles, legends and colour bars match the 2D figures."""

from collections.abc import Callable, Sequence
from pathlib import Path

import numpy as np
import pyvista as pv
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from analytical import bending_stress_at
from benchmark_parameters import BenchmarkParameters
from deck import (
    MIDSPAN_BOTTOM_FLANGE,
    MIDSPAN_TOP_FLANGE,
    TIP_FACE,
    WEB_CENTRELINE_TIP_NODE,
    generate_deck,
)
from figure_data import MeshLevelResults
from frd import FrdResults
from palette import BLUE, EDGES, GREEN, ORANGE, OUTLINE, RED, SECONDARY_INK, STEEL, WALL
from runner import von_mises

TIP_DROP_FRACTION = 0.1
RENDER_SIZE = (2400, 1600)
LOAD = RED
COUPLING = ORANGE
WEB_TIP = BLUE
MIDSPAN = GREEN
STRESS_MAP = "RdBu_r"
DISPLACEMENT_MAP = "viridis"
VON_MISES_MAP = "magma_r"

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
    grid = beam_grid(frd).linear_copy()
    length, h = params.length, params.section.height

    def points(*names: str) -> np.ndarray:
        return np.array([frd.nodes[n] for name in names for n in sets[name]])

    tip_face = points(TIP_FACE)
    midspan = points(MIDSPAN_TOP_FLANGE, MIDSPAN_BOTTOM_FLANGE)
    reference = np.array([length, 0.0, 0.0])
    (web_tip,) = points(WEB_CENTRELINE_TIP_NODE)

    def support(plotter: pv.Plotter) -> None:
        plotter.add_mesh(_wall(params), color=WALL)

    def load(plotter: pv.Plotter) -> None:
        plotter.add_mesh(_load_arrow(reference, params), color=LOAD)

    def overview(plotter: pv.Plotter) -> None:
        _add_surface(plotter, grid)
        support(plotter)
        load(plotter)
        plotter.add_points(midspan, color=MIDSPAN, point_size=14, render_points_as_spheres=True)
        _look(plotter, (1.0, 0.9, 1.7))

    def root(plotter: pv.Plotter) -> None:
        _add_surface(plotter, _cells_where(grid, lambda x: x < 3 * h))
        support(plotter)
        _look(plotter, (1.0, 0.7, 1.3))

    def tip(plotter: pv.Plotter) -> None:
        _add_surface(plotter, _cells_where(grid, lambda x: x > length - 3 * h))
        spokes = pv.PolyData(np.vstack([reference, tip_face]))
        spokes.lines = np.hstack([[2, 0, n] for n in range(1, len(tip_face) + 1)])
        plotter.add_mesh(spokes, color=COUPLING, line_width=3)
        load(plotter)
        plotter.add_mesh(pv.Sphere(radius=7, center=reference), color=LOAD, opacity=0.35)
        plotter.add_mesh(pv.Sphere(radius=3.5, center=web_tip), color=WEB_TIP)
        _look(plotter, (2.6, 0.7, 1.0))

    fig = Figure(figsize=(8, 6.4), layout="constrained")
    grid_spec = fig.add_gridspec(2, 2, height_ratios=(1, 1.5))
    whole, near_root, near_tip = (
        fig.add_subplot(grid_spec[0, :]),
        fig.add_subplot(grid_spec[1, 0]),
        fig.add_subplot(grid_spec[1, 1]),
    )
    _show(whole, _render(overview), f"Solid I-beam, L = {length:g} mm")
    _show(near_root, _render(root), "Root face fixed: u_x = u_y = u_z = 0")
    _show(near_tip, _render(tip), "Tip face: distributing coupling")
    fig.legend(
        handles=[
            Patch(color=WALL, label="fixed root face"),
            Line2D([], [], color=LOAD, linewidth=3, label=f"tip load P = {params.tip_load:g} N"),
            Line2D([], [], color=LOAD, marker="o", alpha=0.6, ls="none", label="reference node"),
            Line2D([], [], color=COUPLING, label="distributing coupling"),
            Line2D([], [], color=WEB_TIP, marker="o", ls="none", label="web-centreline tip node"),
            Line2D([], [], color=MIDSPAN, marker="o", ls="none", label="midspan flange nodes"),
        ],
        loc="outside lower center",
        ncols=3,
    )
    fig.savefig(path)

    return (
        f"The solid I-beam ({level.result.mesh_level.name} mesh), x along the beam, y up. "
        "The root face (x = 0, grey wall) is fixed in all three directions. The tip load "
        f"P = {params.tip_load:g} N acts in −y on the reference node at the tip-face "
        "centroid, and the distributing coupling (orange) spreads it over every tip-face node "
        "without stiffening the face. The reference node is not in the `.frd`, so it is drawn "
        "at its position in the deck. The web-centreline tip node lies on the tip face at the "
        "same point, inside the reference-node marker; its deflection is compared with the "
        "reference node's. The midspan flange nodes (green, x = L/2) cover the outer surfaces "
        "of the top and bottom flanges, where the midspan stress is measured."
    )


def meshes_figure(
    levels: Sequence[MeshLevelResults], params: BenchmarkParameters, path: Path
) -> str:
    root_length = 2 * params.section.height
    section_crop = 0.2 * params.section.height
    fig = Figure(figsize=(8, 2.5 * len(levels)), layout="constrained")
    axes = fig.subplots(len(levels), 2, squeeze=False, width_ratios=(3, 2))
    for (isometric, section), level in zip(axes, levels, strict=True):
        grid = beam_grid(level.frd).linear_copy()
        near_root = _cells_where(grid, lambda x: x < root_length)
        first_slab = _cells_where(grid, lambda x: np.isclose(x, x.min()))
        top_of_section = _cells_where(first_slab, lambda y: y > section_crop, axis=1)

        def iso(plotter: pv.Plotter, mesh: pv.UnstructuredGrid = near_root) -> None:
            _add_edges(plotter, mesh)
            _look(plotter, (1.0, 0.8, 1.6))

        def end_on(plotter: pv.Plotter, mesh: pv.UnstructuredGrid = top_of_section) -> None:
            _add_edges(plotter, mesh)
            _look(plotter, (-1.0, 0.0, 0.0))

        _show(
            isometric,
            _render(iso),
            f"{level.result.mesh_level.label}: {len(level.frd.elements):,} elements, "
            f"{len(level.frd.nodes):,} nodes",
        )
        _show(section, _render(end_on, parallel=True), "cross-section, top flange and web")
    fig.savefig(path)

    names = ", ".join(level.result.mesh_level.label for level in levels)
    return (
        "The mesh levels, labelled with the element counts through the flange thickness, "
        f"along the web height and along the length ({names}). Left: the first "
        f"{root_length:g} mm of the beam from the root face. Right: a close-up of the "
        f"cross-section above y = {section_crop:g} mm, seen along the beam axis (the section "
        "is symmetric about y = 0). The web thickness has as many elements as the flange thickness "
        "and each flange outstand twice as many. All elements are 20-node C3D20R bricks; "
        "their midside nodes are not drawn. The node counts are those in the `.frd`, without "
        "the reference node."
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
        plotter.add_mesh(_outline(grid), color=OUTLINE, line_width=2)
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
        f"displacements scaled × {scale} so that the tip drop ({tip_drop:.2f} mm, the largest "
        f"|u_y|) shows as about {TIP_DROP_FRACTION * 100:g} % of L. The grey outline is the "
        "undeformed beam. u_y is zero at the fixed root face and grows towards the tip like "
        "the deflection curve of figure 5."
    )


def stress_figure(
    levels: Sequence[MeshLevelResults], params: BenchmarkParameters, path: Path
) -> str:
    level = levels[-1]
    name = level.result.mesh_level.name
    grid = beam_grid(level.frd)
    root_bending = bending_stress_at(params, 0.0, params.section.height / 2)
    limit = 10 * np.ceil(root_bending / 10)
    stress_clim = (-limit, limit)
    near_root = _cells_where(grid, lambda x: x < 2 * params.section.height)
    von_mises = near_root.point_data["von_mises"]
    peak = float(von_mises.max())
    mises_clim = (0.0, peak)
    peaks = near_root.points[von_mises >= 0.999 * peak]
    sxx = grid.point_data["sigma_xx"]
    beyond = float(grid.points[np.abs(sxx) > limit, 0].max())

    def from_above(plotter: pv.Plotter) -> None:
        _add_field(plotter, grid, "sigma_xx", STRESS_MAP, stress_clim)
        _look(plotter, (0.5, 0.5, 1.0))

    def from_below(plotter: pv.Plotter) -> None:
        _add_field(plotter, grid, "sigma_xx", STRESS_MAP, stress_clim)
        _look(plotter, (0.5, -0.5, 1.0))

    def root(plotter: pv.Plotter) -> None:
        _add_field(plotter, near_root, "von_mises", VON_MISES_MAP, mises_clim)
        for corner in peaks:
            plotter.add_mesh(pv.Sphere(radius=3, center=corner), color=WEB_TIP)
        _look(plotter, (-1.5, 0.6, 0.8))

    fig = Figure(figsize=(8, 7.4), layout="constrained")
    grid_spec = fig.add_gridspec(3, 1, height_ratios=(1, 1, 2))
    above, below, mises = (fig.add_subplot(grid_spec[row]) for row in range(3))
    _show(above, _render(from_above), f"σ_xx, {name} mesh, from above: top flange in tension")
    _show(below, _render(from_below), "from below: bottom flange in compression")
    _colorbar(fig, [above, below], STRESS_MAP, stress_clim, "σ_xx (MPa)", "vertical", extend="both")
    _show(mises, _render(root), "von Mises near the root, from the support side")
    _colorbar(fig, mises, VON_MISES_MAP, mises_clim, "von Mises (MPa)", "vertical")
    mises.text(
        0.0,
        0.5,
        f"blue dots: peak {peak:.0f} MPa\nat the outer flange\ncorners of the root face",
        transform=mises.transAxes,
        ha="right",
        color=WEB_TIP,
    )
    fig.savefig(path)

    return (
        f"σ_xx on the {name} mesh, seen from above and from below, with a diverging colour "
        "map centred on zero. The hogging moment puts the top flange in tension (red) and the "
        "bottom flange in compression (blue), largest at the root and falling linearly to zero "
        f"at the tip. The colour range is ±{limit:g} MPa, just above the beam-theory root "
        f"bending stress P·L·c/I = {root_bending:.1f} MPa. Only nodes within "
        f"{beyond:.0f} mm of the root face go beyond it, up to ±{np.abs(sxx).max():.0f} MPa. "
        f"Bottom: von Mises stress in the first {2 * params.section.height:g} mm, seen from "
        f"the support side. The peak of {peak:.0f} MPa (blue dots) is at the outer corners of "
        "the flanges on the root face, where the fixed face meets the free surfaces. That is "
        "the stress singularity of a fixed face, which grows with mesh refinement (figure 8), "
        "so the root stress is information only."
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


def _add_surface(plotter: pv.Plotter, grid: pv.UnstructuredGrid) -> None:
    plotter.add_mesh(grid.extract_surface(algorithm=None), color=STEEL, ambient=0.25)


def _add_edges(plotter: pv.Plotter, grid: pv.UnstructuredGrid) -> None:
    plotter.add_mesh(
        grid.extract_surface(algorithm=None),
        color=STEEL,
        ambient=0.25,
        show_edges=True,
        edge_color=EDGES,
        line_width=1.5,
    )


def _add_field(plotter: pv.Plotter, grid, scalars: str, cmap: str, clim) -> None:
    plotter.add_mesh(
        grid.extract_surface(algorithm=None, nonlinear_subdivision=2),
        scalars=scalars,
        cmap=cmap,
        clim=clim,
        ambient=0.5,
        diffuse=0.6,
        show_scalar_bar=False,
    )


def _outline(grid: pv.UnstructuredGrid) -> pv.PolyData:
    return (
        grid.linear_copy()
        .extract_surface(algorithm=None)
        .extract_feature_edges(
            feature_angle=30,
            boundary_edges=False,
            non_manifold_edges=False,
            manifold_edges=False,
        )
    )


def _wall(params: BenchmarkParameters) -> pv.PolyData:
    h, b = params.section.height, params.section.flange_width
    return pv.Box((-0.15 * h, 0.0, -0.75 * h, 0.75 * h, -b, b))


def _load_arrow(reference: np.ndarray, params: BenchmarkParameters) -> pv.PolyData:
    length = 1.3 * params.section.height
    gap = 0.05 * params.section.height
    return pv.Arrow(
        start=reference + [0.0, length + gap, 0.0],
        direction=(0.0, -1.0, 0.0),
        scale=length,
        tip_length=0.15,
        tip_radius=0.04,
        shaft_radius=0.012,
    )


def _cells_where(grid: pv.UnstructuredGrid, keep, axis: int = 0) -> pv.UnstructuredGrid:
    """The cells whose centre coordinate on the axis (default x) passes keep."""
    centres = grid.cell_centers().points[:, axis]
    return grid.extract_cells(np.flatnonzero(keep(centres)))
