"""Draw the figures and write FIGURES.md from the solver output that benchmark.py left behind.

Each entry of FIGURES draws one PNG and returns its caption; the figures page lists them in
order. Exit codes: 0 figures written, 1 a mesh level's results are missing (nothing written).
"""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

import matplotlib
import numpy as np
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter, MaxNLocator

from analytical import (
    analytical_solution,
    bending_stress_at,
    euler_bernoulli_deflection_at,
    timoshenko_deflection_at,
)
from benchmark_parameters import CHS168_CANTILEVER, MESH_LEVELS, BenchmarkParameters
from deck import generate_deck
from figure_data import FigureSeries, MeshLevelResults, figure_series
from frd import read_frd
from palette import AXIS, BAND, BLUE, DARK_BLUE, GREEN, GRID, INK, LIGHT_BLUE, ORANGE, SECONDARY_INK
from renders import deformed_figure, meshes_figure, model_figure, stress_figure
from report import TOLERANCE_PERCENT, observed_order
from runner import benchmark_result, result_files

HERE = Path(__file__).resolve().parent
LEVELS_BY_NAME = {level.name: level for level in MESH_LEVELS}

LEVEL_STYLES = {
    "coarse": {"color": LIGHT_BLUE, "marker": "o"},
    "medium": {"color": BLUE, "marker": "s"},
    "fine": {"color": DARK_BLUE, "marker": "^"},
}
STYLE = {
    "figure.dpi": 150,
    "savefig.dpi": 150,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "font.family": "sans-serif",
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.titleweight": "bold",
    "axes.titlelocation": "left",
    "axes.labelcolor": SECONDARY_INK,
    "axes.edgecolor": AXIS,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.6,
    "xtick.color": SECONDARY_INK,
    "ytick.color": SECONDARY_INK,
    "legend.frameon": False,
    "lines.linewidth": 1.5,
    "lines.markersize": 5,
}


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    levels = [LEVELS_BY_NAME[name] for name in args.levels]
    missing = [
        path
        for level in levels
        for path in result_files(level, args.work_dir)
        if not path.is_file()
    ]
    if missing:
        listed = "\n".join(f"  {path}" for path in missing)
        print(
            f"Missing solver output:\n{listed}\nRun benchmark.py first; no figures written.",
            file=sys.stderr,
        )
        return 1

    params = CHS168_CANTILEVER
    results = []
    for level in levels:
        print(f"Reading mesh level {level.name} ...", flush=True)
        frd_path, dat_path = result_files(level, args.work_dir)
        frd = read_frd(frd_path)
        result = benchmark_result(level, params, generate_deck(params, level), frd, dat_path)
        results.append(MeshLevelResults(result, frd, figure_series(result, frd, params)))

    figures_dir = args.output_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    sections = []
    with matplotlib.rc_context(STYLE):
        for number, slug, title, draw in FIGURES:
            name = f"fig{number}-{slug}.png"
            caption = draw(results, params, figures_dir / name)
            sections.append(_figure_section(number, title, name, caption))
    page = args.output_dir / "FIGURES.md"
    page.write_text(_figures_page(sections))
    print(f"Figures written to {figures_dir} and {page}")
    return 0


def deflection_figure(
    levels: Sequence[MeshLevelResults], params: BenchmarkParameters, path: Path
) -> str:
    x = np.linspace(0, params.length, 301)
    timoshenko = timoshenko_deflection_at(params, x)
    euler_bernoulli = euler_bernoulli_deflection_at(params, x)
    fig, (curve, difference) = _figure(2, 1, figsize=(8, 6.4), sharex=True, height_ratios=(3, 2))

    curve.plot(x, euler_bernoulli, color=SECONDARY_INK, linestyle="--", label="Euler-Bernoulli")
    curve.plot(x, timoshenko, color=INK, linewidth=1, label="Timoshenko, Cowper κ")
    difference.axhline(0, color=INK, linewidth=1, label="Timoshenko")
    for level in levels:
        s = level.series
        style = _level_line_style(s)
        curve.plot(s.deflection_x, s.deflection_v, **style)
        difference.plot(
            s.deflection_x,
            s.deflection_v - timoshenko_deflection_at(params, s.deflection_x),
            **style,
        )

    tip = levels[-1].series.convergence
    tip_target = timoshenko_deflection_at(params, params.length)
    reference = {"color": INK, "marker": "D", "markersize": 7, "markerfacecolor": "white"}
    curve.plot(
        params.length,
        tip.reference_node_deflection,
        linestyle="none",
        **reference,
        label=f"reference node ({levels[-1].series.mesh_level.name})",
    )
    difference.plot(
        params.length, tip.reference_node_deflection - tip_target, linestyle="none", **reference
    )
    curve.annotate(
        f"reference node δ = {tip.reference_node_deflection:.5f} mm\n"
        f"Timoshenko δ_T = {tip_target:.5f} mm\n"
        f"Euler-Bernoulli δ_EB = {euler_bernoulli[-1]:.5f} mm",
        (params.length, tip.reference_node_deflection),
        xytext=(0.62, 0.95),
        textcoords="axes fraction",
        ha="right",
        va="top",
        color=INK,
        arrowprops={"arrowstyle": "-", "color": SECONDARY_INK, "linewidth": 0.8, "shrinkB": 6},
    )

    curve.set_title("Deflection v(x), mean over each node plane")
    curve.set_ylabel("downward deflection v (mm)")
    curve.legend(loc="upper left")
    difference.set_title("Difference from Timoshenko", fontsize=9)
    difference.set_ylabel("v − v_T (mm)")
    difference.set_xlabel("x from the root face (mm)")
    difference.legend(loc="lower left", ncols=4)
    fig.savefig(path)

    fine = levels[-1].series
    gap = fine.deflection_v - timoshenko_deflection_at(params, fine.deflection_x)
    shear_term = tip_target - euler_bernoulli[-1]
    return (
        "Downward deflection v(x), the mean −u_y over all nodes of each node plane, for each "
        "mesh level against the Euler-Bernoulli curve P·x²(3L − x)/(6EI) and the Timoshenko "
        "curve, which adds the shear term P·x/(κ·G·A) with Cowper's κ. The tube is short "
        f"(L/D ≈ {params.length / (2 * params.section.outer_radius):.0f}), so shear is "
        f"{shear_term / tip_target * 100:.1f} % of the tip deflection: the FE curves lie on "
        "the Timoshenko curve, while the Euler-Bernoulli curve ends "
        f"{shear_term:.4f} mm short at the tip. The lower panel shows the FE difference from "
        f"Timoshenko: for the {fine.mesh_level.name} level it rises to {gap.max():+.4f} mm "
        f"near the root, falls steadily to {gap.min():+.4f} mm "
        f"({np.abs(gap).max() / tip_target * 100:.2f} % of δ_T) just before the tip, where the "
        "distributing coupling brings the load in, and comes back to "
        f"{gap[-1]:+.4f} mm at the tip face. At the tip the node-plane mean is the tip-face "
        "mean deflection of REPORT.md. The "
        "diamond is the reference node's tip deflection from the `.dat`, the pass/fail value "
        f"({tip.deflection_error:+.3f} % against δ_T)."
    )


def circumference_stress_figure(
    levels: Sequence[MeshLevelResults], params: BenchmarkParameters, path: Path
) -> str:
    a = analytical_solution(params)
    midspan = params.length / 2
    r_o = params.section.outer_radius
    y = np.linspace(-r_o, r_o, 101)
    fig, (profile, difference) = _figure(1, 2, figsize=(8, 5.2), sharey=True, width_ratios=(3, 2))

    profile.plot(bending_stress_at(params, midspan, y), y, color=INK, linewidth=1, label="M·y/I")
    difference.axvline(0, color=INK, linewidth=1)
    for level in levels:
        s = level.series
        style = _level_marker_style(s)
        profile.plot(s.circumference_sxx, s.circumference_y, **style)
        expected = bending_stress_at(params, midspan, s.circumference_y)
        difference.plot(s.circumference_sxx - expected, s.circumference_y, **style)

    profile.set_title("σ_xx around the outer surface at x = L/2")
    profile.set_xlabel("σ_xx (MPa)")
    profile.set_ylabel("y from the neutral axis (mm)")
    profile.legend(loc="upper left")
    difference.set_title("Difference from M·y/I", fontsize=9)
    difference.set_xlabel("σ_xx − M·y/I (MPa)")
    difference.xaxis.set_major_locator(MaxNLocator(5))
    fig.savefig(path)

    coarse, fine = levels[0], levels[-1]
    coarse_gap = coarse.series.circumference_sxx - bending_stress_at(
        params, midspan, coarse.series.circumference_y
    )
    fine_gap = fine.series.circumference_sxx - bending_stress_at(
        params, midspan, fine.series.circumference_y
    )
    return (
        "Nodal σ_xx of every outer-surface node at midspan (x = L/2), corner and midside, "
        "against its height y, for each mesh level, with the beam-theory distribution M·y/I "
        "and M = P·L/2. These are the nodes of the midspan stress fit σ_xx = a·y. Plane "
        "sections stay plane: σ_xx is linear in y, zero at the neutral axis and "
        f"±{a.midspan_stress:.2f} MPa at the top and bottom fibres, tension at the top and "
        "compression at the bottom under the hogging moment. Nodes at the same height on "
        "either side of the section (±z) carry the same stress, so their markers overlap. The "
        "right panel shows the section discretisation error: the "
        f"{coarse.result.mesh_level.name} level "
        f"({coarse.result.mesh_level.circumferential_divisions} elements around) swings about "
        f"M·y/I from node to node by up to {np.abs(coarse_gap).max():.2f} MPa, most at the "
        f"fibres ({coarse.result.top_fibre_stress_error:+.1f} % at the top-fibre node). The "
        "fit over all the nodes averages the swings out, which is why its error "
        f"({coarse.result.midspan_top_stress_error:+.2f} %) is smaller than the single-node one. "
        f"The {fine.result.mesh_level.name} level differs from M·y/I by at most "
        f"{np.abs(fine_gap).max():.3f} MPa."
    )


def top_fibre_stress_figure(
    levels: Sequence[MeshLevelResults], params: BenchmarkParameters, path: Path
) -> str:
    a = analytical_solution(params)
    length, d = params.length, 2 * params.section.outer_radius

    def moment_diagram(x):
        return bending_stress_at(params, x, a.outer_fibre_distance)

    x = np.linspace(0, length, 301)
    fig, (along, difference) = _figure(2, 1, figsize=(8, 6.4), sharex=True, height_ratios=(3, 2))
    for ax in (along, difference):
        ax.axvspan(0, d, color=BAND, linewidth=0, zorder=0)
        ax.axvspan(length - d, length, color=BAND, linewidth=0, zorder=0)
    along.plot(x, moment_diagram(x), color=INK, linewidth=1, label="P·(L − x)·r_o/I")
    difference.axhline(0, color=INK, linewidth=1)
    for level in levels:
        s = level.series
        style = _level_line_style(s)
        along.plot(s.top_fibre_x, s.top_fibre_sxx, **style)
        difference.plot(s.top_fibre_x, s.top_fibre_sxx - moment_diagram(s.top_fibre_x), **style)
    for centre, label in ((d / 2, "root\nzone"), (length - d / 2, "tip\nzone")):
        difference.text(
            centre,
            0.97,
            label,
            transform=difference.get_xaxis_transform(),
            ha="center",
            va="top",
            color=SECONDARY_INK,
        )

    along.set_title("σ_xx along the top fibre (y = r_o, z = 0)")
    along.set_ylabel("σ_xx (MPa)")
    along.legend(loc="upper right")
    difference.set_title("Difference from the moment diagram", fontsize=9)
    difference.set_ylabel("σ_xx − P·(L − x)·r_o/I (MPa)")
    difference.set_xlabel("x from the root face (mm)")
    fig.savefig(path)

    middle_errors = []
    for level in levels:
        s = level.series
        middle = (s.top_fibre_x >= d) & (s.top_fibre_x <= length - d)
        relative = s.top_fibre_sxx[middle] / moment_diagram(s.top_fibre_x[middle]) - 1
        middle_errors.append(f"{np.abs(relative).max() * 100:.1f}")
    names = " → ".join(level.result.mesh_level.name for level in levels)
    return (
        "Nodal σ_xx along the top fibre of the outer surface (y = r_o, z = 0) for each mesh "
        "level against the linear moment diagram σ = P·(L − x)·r_o/I. More than one diameter "
        f"(D = {d:g} mm, shaded) from either end the largest difference from beam theory falls "
        f"{' → '.join(middle_errors)} % ({names}): the single-node section discretisation "
        "error of figure 6, which is about the same all along the tube. The "
        f"{levels[0].result.mesh_level.name} curve also swings between the corner and midside "
        "nodes of its "
        f"{length / levels[0].result.mesh_level.length_divisions:g} mm long elements. The "
        "shaded St-Venant zones are where the end conditions "
        "disturb the beam-theory stress: at the root the fixed face stops the lateral "
        "(Poisson) contraction, and at the tip the distributing coupling brings the load in "
        "over the tip face."
    )


def convergence_figure(
    levels: Sequence[MeshLevelResults], params: BenchmarkParameters, path: Path
) -> str:
    root_bending = bending_stress_at(params, 0.0, analytical_solution(params).outer_fibre_distance)
    points = [level.series.convergence for level in levels]
    sizes = [p.element_size for p in points]
    names = [level.series.mesh_level.name for level in levels]
    quantities = (
        ("tip deflection vs δ_T", "o", BLUE, [p.deflection_error for p in points]),
        ("midspan stress fit", "^", ORANGE, [p.fitted_stress_errors[0] for p in points]),
        ("single-node fibre stress", "s", GREEN, [p.single_node_stress_errors[0] for p in points]),
    )
    fig, (errors_view, root) = _figure(1, 2, figsize=(10, 4.8), width_ratios=(3, 2))

    errors_view.axhline(TOLERANCE_PERCENT, color=SECONDARY_INK, linewidth=1, linestyle="--")
    errors_view.text(
        sizes[-1],
        TOLERANCE_PERCENT * 0.92,
        f"{TOLERANCE_PERCENT:g} % pass limit",
        va="top",
        color=SECONDARY_INK,
    )
    orders = []
    for label, marker, color, errors in quantities:
        order = observed_order(errors) if len(errors) == 3 else None
        orders.append(order)
        order_text = "p n/a" if order is None else f"p = {order:.2f}"
        errors_view.plot(
            sizes, np.abs(errors), marker=marker, color=color, markersize=7, label=label
        )
        negative = [(size, -e) for size, e in zip(sizes, errors, strict=True) if e < 0]
        if negative:
            errors_view.plot(
                *zip(*negative, strict=True),
                linestyle="none",
                marker=marker,
                color=color,
                markersize=7,
                markerfacecolor="white",
            )
        errors_view.annotate(
            order_text,
            (sizes[0], abs(errors[0])),
            xytext=(8, 0),
            textcoords="offset points",
            va="center",
            color=INK,
        )
    errors_view.set_xscale("log")
    errors_view.set_yscale("log")
    errors_view.set_title("|Signed error| against element size, log-log")
    errors_view.set_ylabel("|error| (%)")
    errors_view.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:g}"))
    errors_view.plot(
        [],
        [],
        linestyle="none",
        marker="o",
        color=INK,
        markerfacecolor="white",
        label="hollow: negative signed error",
    )
    errors_view.legend(loc="upper left")

    root.axhline(root_bending, color=INK, linewidth=1, linestyle="--")
    root.annotate(
        f"beam theory P·L·r_o/I = {root_bending:.1f} MPa",
        (sizes[0], root_bending),
        xytext=(0, -4),
        textcoords="offset points",
        ha="right",
        va="top",
        color=INK,
    )
    root.plot(
        sizes,
        [p.root_peak_von_mises for p in points],
        marker="o",
        color=INK,
        markersize=7,
        label="FE peak on the root face",
    )
    for size, p in zip(sizes, points, strict=True):
        root.annotate(
            f"{p.root_peak_von_mises:.1f}",
            (size, p.root_peak_von_mises),
            xytext=(6, 4),
            textcoords="offset points",
            color=INK,
        )
    root.set_xscale("log")
    root.set_title("Root peak von Mises (information only)")
    root.set_ylabel("von Mises (MPa)")
    root.set_ylim(0.9 * root_bending, 1.1 * max(p.root_peak_von_mises for p in points))
    root.legend(loc="upper right")

    for ax in (errors_view, root):
        ax.set_xticks(sizes, [f"{name}\n{s:.1f} mm" for name, s in zip(names, sizes, strict=True)])
        ax.minorticks_off()
        ax.margins(x=0.15)
    fig.supxlabel(
        "element size: outer arc length per element, 2π·r_o / circumferential divisions "
        "(log scale)",
        color=SECONDARY_INK,
        fontsize=9,
    )
    fig.savefig(path)

    fit, single = orders[1], orders[2]
    roots = " → ".join(f"{p.root_peak_von_mises:.1f}" for p in points)
    deflections = " → ".join(f"{p.deflection_error:+.3f}" for p in points)

    def order_phrase(order: float | None) -> str:
        return "not available" if order is None else f"p = {order:.2f}"

    return (
        "Convergence against element size, one point per mesh level, on log-log axes. The "
        "element size is the arc length of one element along the outer circumference, "
        "2π·r_o / circumferential divisions; every level halves it, along with the element "
        "size through the wall and along the length. Left: the magnitude of the signed error "
        "of each quantity against its target (hollow markers where the signed error is "
        "negative), labelled with its observed order p = "
        "ln((e_c − e_m)/(e_m − e_f)) / ln 2 from REPORT.md. The bottom-fibre errors equal the "
        "top-fibre ones (the fit gives ±a·r_o and the section is symmetric), so only the top "
        "is drawn. The midspan stress fit converges with "
        f"{order_phrase(fit)} and the single-node fibre stress with {order_phrase(single)}: "
        "that is the section discretisation error falling as the circle is resolved. The "
        f"deflection error ({deflections} %) is already within 0.1 % at the coarse level, "
        "changes sign and then sits on the modelling floor between the clamped solid and "
        "Timoshenko beam theory, so its order is not available. Right: the root peak von Mises "
        f"stress ({roots} MPa) against the beam-theory root bending stress "
        f"P·L·r_o/I = {root_bending:.1f} MPa; it grows with refinement because of the fixed "
        "root face, which is why it is information only and does not enter the verdict."
    )


FIGURES = (
    (1, "model", "Model and boundary conditions", model_figure),
    (2, "meshes", "Mesh levels", meshes_figure),
    (3, "deformed-shape", "Deformed shape", deformed_figure),
    (4, "stress", "σ_xx and von Mises stress", stress_figure),
    (5, "deflection", "Deflection along the beam", deflection_figure),
    (
        6,
        "stress-around-circumference",
        "σ_xx around the circumference at midspan",
        circumference_stress_figure,
    ),
    (7, "stress-along-top-fibre", "σ_xx along the top fibre", top_fibre_stress_figure),
    (8, "convergence", "Convergence against element size", convergence_figure),
)
"""(number, file slug, title, draw). draw(levels, params, path) writes the PNG and returns the
caption."""


def _figure(nrows: int, ncols: int, figsize: tuple[float, float], **gridspec):
    fig = Figure(figsize=figsize, layout="constrained")
    share = {key: gridspec.pop(key) for key in ("sharex", "sharey") if key in gridspec}
    axes = fig.subplots(nrows, ncols, gridspec_kw=gridspec, **share)
    return fig, axes


def _level_line_style(series: FigureSeries) -> dict:
    style = LEVEL_STYLES[series.mesh_level.name]
    return {**style, "label": series.mesh_level.name, "markevery": 0.1, "markersize": 5}


def _level_marker_style(series: FigureSeries) -> dict:
    style = LEVEL_STYLES[series.mesh_level.name]
    return {
        **style,
        "label": series.mesh_level.name,
        "linestyle": "none",
        "markerfacecolor": "white",
    }


def _figure_section(number: int, title: str, name: str, caption: str) -> str:
    return (
        f"## Figure {number}. {title}\n\n![Figure {number}: {title}](figures/{name})\n\n{caption}\n"
    )


def _figures_page(sections: list[str]) -> str:
    header = [
        "# CHS 168.3 × 8 tube cantilever benchmark figures",
        "",
        "Generated by `python plots.py` from the solver output of `python benchmark.py`. "
        "Do not edit by hand. The numbers are in [REPORT.md](REPORT.md).",
        "",
    ]
    return "\n".join(header) + "\n" + "\n".join(sections)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--levels",
        nargs="+",
        choices=list(LEVELS_BY_NAME),
        default=list(LEVELS_BY_NAME),
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--work-dir", type=Path, default=HERE / "work")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=HERE,
        help="where figures/ and FIGURES.md go (default: this folder)",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
