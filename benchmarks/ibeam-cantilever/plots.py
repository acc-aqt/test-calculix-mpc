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
from matplotlib.ticker import MaxNLocator

from analytical import (
    analytical_solution,
    bending_stress_at,
    euler_bernoulli_deflection_at,
    timoshenko_deflection_at,
)
from benchmark_parameters import IPE200_CANTILEVER, MESH_LEVELS, BenchmarkParameters
from deck import generate_deck
from figure_data import FigureSeries, MeshLevelResults, figure_series
from frd import read_frd
from palette import AXIS, BAND, BLUE, DARK_BLUE, GREEN, GRID, INK, LIGHT_BLUE, ORANGE, SECONDARY_INK
from renders import deformed_figure, meshes_figure, model_figure, stress_figure
from report import TOLERANCE_PERCENT
from runner import benchmark_result, result_files

HERE = Path(__file__).resolve().parent
LEVELS_BY_NAME = {level.name: level for level in MESH_LEVELS}

LEVEL_STYLES = {
    "coarse": {"color": LIGHT_BLUE, "marker": "o"},
    "medium": {"color": BLUE, "marker": "s"},
    "fine": {"color": DARK_BLUE, "marker": "^"},
}
QUANTITY_COLORS = (BLUE, ORANGE, GREEN)
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

    params = IPE200_CANTILEVER
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
    curve.plot(x, timoshenko, color=INK, linewidth=1, label="Timoshenko")
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
        f"reference node δ = {tip.reference_node_deflection:.3f} mm\n"
        f"Timoshenko δ_T = {tip_target:.3f} mm",
        (params.length, tip.reference_node_deflection),
        xytext=(0.62, 0.95),
        textcoords="axes fraction",
        ha="right",
        va="top",
        color=INK,
        arrowprops={"arrowstyle": "-", "color": SECONDARY_INK, "linewidth": 0.8, "shrinkB": 6},
    )

    curve.set_title("Deflection v(x) on the web centreline")
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
        "Downward deflection v(x) of the web-centreline nodes for each mesh level against the "
        "Euler-Bernoulli curve P·x²(3L − x)/(6EI) and the Timoshenko curve, which adds the "
        "shear term P·x/(κ·G·A_s). The FE curves lie on the Timoshenko curve along the whole "
        "beam, while the Euler-Bernoulli curve, which leaves out shear, ends "
        f"{shear_term:.3f} mm short at the tip. The lower panel shows the FE difference from "
        f"Timoshenko: for the {fine.mesh_level.name} level at most "
        f"{np.abs(gap).max():.3f} mm, {np.abs(gap).max() / tip_target * 100:.2f} % of δ_T. "
        "The FE beam is slightly stiffer than Timoshenko theory with A_s = (h − t_f)·t_w and "
        "κ = 1. The difference drops quickly in the first 100 mm, where the fixed root face "
        "holds back the shear deformation that Timoshenko theory has from x = 0, then grows "
        "steadily along the beam and dips again in the last section depth, where the "
        "distributing coupling brings the load into the tip face. The diamond is the "
        "reference node's tip deflection from the `.dat`, the pass/fail value "
        f"({tip.deflection_error:+.3f} % against Timoshenko); it sits closer to Timoshenko than "
        "the web-centreline tip node because the coupling averages the tip-face motion."
    )


def depth_stress_figure(
    levels: Sequence[MeshLevelResults], params: BenchmarkParameters, path: Path
) -> str:
    a = analytical_solution(params)
    midspan = params.length / 2
    half_h, t_f = params.section.height / 2, params.section.flange_thickness
    y = np.linspace(-half_h, half_h, 101)
    fig, (profile, difference) = _figure(1, 2, figsize=(8, 5.2), sharey=True, width_ratios=(3, 2))

    for ax in (profile, difference):
        for edge in (-half_h, half_h - t_f):
            ax.axhspan(edge, edge + t_f, color=BAND, linewidth=0, zorder=0)
    profile.text(-80, half_h - t_f / 2, "top flange", va="center", color=SECONDARY_INK)
    profile.text(
        80, -half_h + t_f / 2, "bottom flange", va="center", ha="right", color=SECONDARY_INK
    )
    profile.plot(bending_stress_at(params, midspan, y), y, color=INK, linewidth=1, label="M·y/I")
    difference.axvline(0, color=INK, linewidth=1)
    for level in levels:
        s = level.series
        style = _level_marker_style(s)
        profile.plot(s.depth_sxx, s.depth_y, **style)
        expected = bending_stress_at(params, midspan, s.depth_y)
        difference.plot(s.depth_sxx - expected, s.depth_y, **style)

    profile.set_title("σ_xx through the depth at x = L/2 (z = 0)")
    profile.set_xlabel("σ_xx (MPa)")
    profile.set_ylabel("y from the neutral axis (mm)")
    profile.legend(loc="upper left", bbox_to_anchor=(0, 0.92))
    difference.set_title("Difference from M·y/I", fontsize=9)
    difference.set_xlabel("σ_xx − M·y/I (MPa)")
    difference.xaxis.set_major_locator(MaxNLocator(5))
    fig.savefig(path)

    fine = levels[-1].series
    expected = bending_stress_at(params, midspan, fine.depth_y)
    return (
        "Nodal σ_xx at midspan (x = L/2) on the mid-plane z = 0, through the web and both "
        "flanges, for each mesh level against the linear beam-theory distribution M·y/I with "
        f"M = P·L/2. The shaded bands are the flanges. Plane sections stay plane: σ_xx is "
        f"linear in y, zero at the neutral axis and ±{a.midspan_stress:.2f} MPa at the outer "
        "fibres, tension at the top and compression at the bottom under the hogging moment. "
        f"The {fine.mesh_level.name} level differs from M·y/I by at most "
        f"{np.abs(fine.depth_sxx - expected).max():.3f} MPa (right panel)."
    )


def flange_stress_figure(
    levels: Sequence[MeshLevelResults], params: BenchmarkParameters, path: Path
) -> str:
    a = analytical_solution(params)
    length, h = params.length, params.section.height

    def moment_diagram(x):
        return bending_stress_at(params, x, a.outer_fibre_distance)

    x = np.linspace(0, length, 301)
    fig, (along, difference) = _figure(2, 1, figsize=(8, 6.4), sharex=True, height_ratios=(3, 2))
    for ax in (along, difference):
        ax.axvspan(0, h, color=BAND, linewidth=0, zorder=0)
        ax.axvspan(length - h, length, color=BAND, linewidth=0, zorder=0)
    along.plot(x, moment_diagram(x), color=INK, linewidth=1, label="P·(L − x)·c/I")
    difference.axhline(0, color=INK, linewidth=1)
    for level in levels:
        s = level.series
        style = _level_line_style(s)
        along.plot(s.top_flange_x, s.top_flange_sxx, **style)
        difference.plot(s.top_flange_x, s.top_flange_sxx - moment_diagram(s.top_flange_x), **style)
    difference.text(
        h / 2,
        0.97,
        "root\nzone",
        transform=difference.get_xaxis_transform(),
        ha="center",
        va="top",
        color=SECONDARY_INK,
    )
    difference.text(
        length - h / 2,
        0.97,
        "tip\nzone",
        transform=difference.get_xaxis_transform(),
        ha="center",
        va="top",
        color=SECONDARY_INK,
    )

    along.set_title("σ_xx on the top flange outer surface, mean across the width")
    along.set_ylabel("σ_xx (MPa)")
    along.legend(loc="upper right")
    difference.set_title("Difference from the moment diagram", fontsize=9)
    difference.set_ylabel("σ_xx − P·(L − x)·c/I (MPa)")
    difference.set_xlabel("x from the root face (mm)")
    fig.savefig(path)

    fine = levels[-1].series
    gap = fine.top_flange_sxx - moment_diagram(fine.top_flange_x)
    middle = (fine.top_flange_x >= h) & (fine.top_flange_x <= length - h)
    return (
        "Nodal σ_xx on the outer surface of the top flange (y = h/2), averaged across the "
        "flange width at each node plane, for each mesh level against the linear moment "
        "diagram σ = P·(L − x)·c/I. More than one section depth (h = "
        f"{h:g} mm, shaded) from either end the {fine.mesh_level.name} level differs from "
        f"beam theory by at most {np.abs(gap[middle]).max():.2f} MPa. The shaded St-Venant "
        "zones are where the end conditions disturb the beam-theory stress. At the root the "
        "fixed root face stops the lateral (Poisson) contraction and the stress is singular "
        "where it meets the free surfaces, so the flange stress at x = 0 rises from coarse to "
        "fine ("
        + " → ".join(f"{level.series.top_flange_sxx[0]:.0f}" for level in levels)
        + f" MPa against P·L·c/I = {moment_diagram(0.0):.1f} MPa) and undershoots just "
        "behind it. At the tip the distributing coupling brings the load in over the tip "
        "face, which adds a local σ_xx of up to "
        f"{gap[fine.top_flange_x > length - h].max():.0f} MPa where beam theory has almost none."
    )


def convergence_figure(
    levels: Sequence[MeshLevelResults], params: BenchmarkParameters, path: Path
) -> str:
    root_bending = bending_stress_at(params, 0.0, analytical_solution(params).outer_fibre_distance)
    points = [level.series.convergence for level in levels]
    nodes = [p.node_count for p in points]
    names = [level.series.mesh_level.name for level in levels]
    quantities = (
        ("tip deflection vs Timoshenko", "o", [p.deflection_error for p in points]),
        ("midspan σ_xx, top flange", "^", [p.top_stress_error for p in points]),
        ("midspan σ_xx, bottom flange", "v", [p.bottom_stress_error for p in points]),
    )
    fig, (band_view, close_view, root) = _figure(1, 3, figsize=(13, 4.4))

    for ax in (band_view, close_view):
        ax.axhspan(-TOLERANCE_PERCENT, TOLERANCE_PERCENT, color=BAND, linewidth=0, zorder=0)
        ax.axhline(0, color=AXIS, linewidth=1)
        for (label, marker, errors), color in zip(quantities, QUANTITY_COLORS, strict=True):
            hollow = marker == "v"
            ax.plot(
                nodes,
                errors,
                marker=marker,
                color=color,
                label=label,
                markerfacecolor="white" if hollow else color,
                markersize=7,
            )
    band_view.set_ylim(-1.25 * TOLERANCE_PERCENT, 1.25 * TOLERANCE_PERCENT)
    all_errors = [0.0, *(e for _, _, errors in quantities for e in errors)]
    pad = 0.25 * (max(all_errors) - min(all_errors))
    close_view.set_ylim(min(all_errors) - pad, max(all_errors) + pad)
    band_view.text(
        nodes[0],
        TOLERANCE_PERCENT,
        f"+{TOLERANCE_PERCENT:g} % pass band edge",
        va="bottom",
        color=SECONDARY_INK,
    )
    band_view.text(
        nodes[0],
        -TOLERANCE_PERCENT,
        f"−{TOLERANCE_PERCENT:g} % pass band edge",
        va="top",
        color=SECONDARY_INK,
    )
    band_view.set_title(f"Signed error, ±{TOLERANCE_PERCENT:g} % pass band")
    close_view.set_title("Same errors, close up (all inside the band)")
    band_view.set_ylabel("error (%)")
    close_view.legend(loc="lower right")

    root.axhline(root_bending, color=INK, linewidth=1, linestyle="--")
    root.annotate(
        f"beam theory P·L·c/I = {root_bending:.1f} MPa",
        (nodes[-1], root_bending),
        xytext=(0, -4),
        textcoords="offset points",
        ha="right",
        va="top",
        color=INK,
    )
    root.plot(
        nodes,
        [p.root_peak_von_mises for p in points],
        marker="o",
        color=INK,
        markersize=7,
        label="FE peak on the root face",
    )
    for n, p in zip(nodes, points, strict=True):
        root.annotate(
            f"{p.root_peak_von_mises:.0f}",
            (n, p.root_peak_von_mises),
            xytext=(6, -10),
            textcoords="offset points",
            color=INK,
        )
    root.set_title("Root peak von Mises (information only)")
    root.set_ylabel("von Mises (MPa)")
    root.set_ylim(0.9 * root_bending, 1.1 * max(p.root_peak_von_mises for p in points))
    root.legend(loc="upper left")

    for ax in (band_view, close_view, root):
        ax.set_xscale("log")
        ax.set_xticks(nodes, [f"{name}\n{n:,}" for name, n in zip(names, nodes, strict=True)])
        ax.minorticks_off()
        ax.set_xlabel("nodes, including the reference node (log scale)")
        ax.margins(x=0.15)
    fig.savefig(path)

    span = max(max(abs(e) for e in errors) for _, _, errors in quantities)
    roots = " → ".join(f"{p.root_peak_von_mises:.0f}" for p in points)
    return (
        "Convergence against node count (log scale), one point per mesh level. As in "
        "REPORT.md and figure 2, the node counts include the reference node. Left: the "
        "signed errors of the three pass/fail quantities against their targets, inside the "
        f"shaded ±{TOLERANCE_PERCENT:g} % pass band. Middle: the same errors close up. Every "
        f"level is within {span:.3f} % of its target, so the results are stable from coarse "
        "to fine; the top- and bottom-flange stress errors are equal and their markers "
        "overlap. Right: the root peak von Mises stress grows from each mesh level to the next "
        f"({roots} MPa) and moves away from the beam-theory root bending stress "
        f"P·L·c/I = {root_bending:.1f} MPa. That is the expected stress singularity "
        "where the fixed root face meets the free surfaces, which is why the root stress is "
        "information only and does not enter the verdict."
    )


FIGURES = (
    (1, "model", "Model and boundary conditions", model_figure),
    (2, "meshes", "Mesh levels", meshes_figure),
    (3, "deformed-shape", "Deformed shape", deformed_figure),
    (4, "stress", "σ_xx and von Mises stress", stress_figure),
    (5, "deflection", "Deflection along the beam", deflection_figure),
    (6, "stress-through-depth", "σ_xx through the depth at midspan", depth_stress_figure),
    (7, "stress-along-flange", "σ_xx along the top flange", flange_stress_figure),
    (8, "convergence", "Convergence against mesh size", convergence_figure),
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
        "# IPE 200 cantilever benchmark figures",
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
