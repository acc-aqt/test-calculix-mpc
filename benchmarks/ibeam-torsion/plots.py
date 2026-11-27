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
from matplotlib.ticker import FuncFormatter

from analytical import analytical_solution, st_venant_twist_at, twist_at, warping_stress_at
from benchmark_parameters import IPE200_TORSION, MESH_LEVELS, BenchmarkParameters
from deck import generate_deck
from figure_data import FigureSeries, MeshLevelResults, figure_series
from frd import read_frd
from palette import AXIS, BAND, BLUE, DARK_BLUE, GRID, INK, LIGHT_BLUE, ORANGE, SECONDARY_INK
from renders import stress_figure
from report import FOLLOW_UP, TIP_TWIST_TOLERANCE_PERCENT, WARPING_STRESS_TOLERANCE_PERCENT
from runner import ONSET_MARGIN, PLATEAU_RANGE, benchmark_result, result_files, tip_zone

HERE = Path(__file__).resolve().parent
LEVELS_BY_NAME = {level.name: level for level in MESH_LEVELS}

LEVEL_STYLES = {
    "coarse": {"color": LIGHT_BLUE, "marker": "o"},
    "medium": {"color": BLUE, "marker": "s"},
    "fine": {"color": DARK_BLUE, "marker": "^"},
}
MARKER_SIZES = {"coarse": 9, "medium": 6.5, "fine": 4.5}
"""Shrinking from coarse to fine, so markers of levels that share a node position stay visible."""
END_CORRECTED = {"color": SECONDARY_INK, "linewidth": 0.8, "linestyle": ":"}
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
    levels = [level for level in MESH_LEVELS if level.name in args.levels]
    frd_paths = [result_files(level, args.work_dir)[0] for level in levels]
    missing = [path for path in frd_paths if not path.is_file()]
    if missing:
        listed = "\n".join(f"  {path}" for path in missing)
        print(
            f"Missing solver output:\n{listed}\nRun benchmark.py first; no figures written.",
            file=sys.stderr,
        )
        return 1

    params = IPE200_TORSION
    results = []
    for level, frd_path in zip(levels, frd_paths, strict=True):
        print(f"Reading mesh level {level.name} ...", flush=True)
        frd = read_frd(frd_path)
        deck = generate_deck(params, level)
        result = benchmark_result(level, params, deck, frd)
        results.append(MeshLevelResults(result, frd, figure_series(result, frd, deck)))

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


def twist_figure(
    levels: Sequence[MeshLevelResults], params: BenchmarkParameters, path: Path
) -> str:
    a = analytical_solution(params)
    j_corrected = a.end_corrected_torsion_constant
    x = np.linspace(0, params.length, 301)
    vlasov = twist_at(params, x)
    corrected = twist_at(params, x, torsion_constant=j_corrected)
    fig, (curve, difference) = _figure(2, 1, figsize=(8, 6.4), sharex=True, height_ratios=(3, 2))

    curve.plot(
        x, st_venant_twist_at(params, x), color=SECONDARY_INK, linestyle="--", label="St-Venant"
    )
    curve.plot(x, vlasov, color=INK, linewidth=1, label="Vlasov (target)")
    curve.plot(x, corrected, **END_CORRECTED, label="Vlasov, end-corrected J (information)")
    difference.axhline(0, color=INK, linewidth=1)
    difference.plot(x, (corrected - vlasov) * 1000, **END_CORRECTED)
    for level in levels:
        s = level.series
        style = _level_line_style(s)
        curve.plot(s.twist_x, s.twist_phi, **style)
        difference.plot(s.twist_x, (s.twist_phi - twist_at(params, s.twist_x)) * 1000, **style)

    curve.set_title("Twist φ(x) = (u_z,top − u_z,bottom)/h_m")
    curve.set_ylabel("φ (rad)")
    curve.legend(loc="upper left")
    difference.set_title("Difference from Vlasov", fontsize=9)
    difference.set_ylabel("φ − φ_Vlasov (mrad)")
    difference.set_xlabel("x from the root face (mm)")
    fig.savefig(path)

    fine = levels[-1]
    gap = fine.series.twist_phi - twist_at(params, fine.series.twist_x)
    midspan = np.isclose(fine.series.twist_x, params.length / 2)
    midspan_error = gap[midspan][0] / twist_at(params, params.length / 2) * 100
    return (
        "Twist φ(x) from the flange mid-plane centre nodes at every x station, for each mesh "
        "level, against the Vlasov curve of mixed torsion (the target, root warping-restrained "
        "and tip free to warp) and the pure St-Venant line T·x/(GJ). Restraining warping at the "
        f"root stiffens the beam: the Vlasov tip twist is {a.tip_twist:.4f} rad, "
        f"{a.tip_twist / a.st_venant_tip_twist * 100:.0f} % of the St-Venant "
        f"{a.st_venant_tip_twist:.4f} rad. Near the root φ grows slowly, because warping carries "
        "most of the torque there, and towards the tip it runs parallel to the St-Venant line. "
        "The FE curves of the three levels nearly coincide and lie above Vlasov; the lower panel "
        "shows the gap growing smoothly from the root to "
        f"{gap[-1] * 1000:+.1f} mrad ({fine.result.tip_twist_error:+.2f} %) at the tip on the "
        f"{fine.result.mesh_level.name} level, {midspan_error:+.1f} % at midspan. Most of it is "
        "the thin-walled torsion constant, which leaves out the plate-end correction and so "
        "overstates the solid's St-Venant stiffness. The dotted line (information) is Vlasov "
        f"with the end-corrected J = {j_corrected:.0f} mm⁴, which ends at "
        f"{a.end_corrected_tip_twist:.4f} rad. The FE gap follows it up to about two thirds of "
        "the length and then grows past it, over the stretch where figure 3 shows the "
        "disturbance from the load introduction (follow-up "
        f"{FOLLOW_UP})."
    )


def flange_width_stress_figure(
    levels: Sequence[MeshLevelResults], params: BenchmarkParameters, path: Path
) -> str:
    a = analytical_solution(params)
    s = params.section
    x = params.length / 4
    half_web = s.web_thickness / 2
    y_mid = a.flange_mid_plane_distance / 2
    z = np.linspace(-s.flange_width / 2, s.flange_width / 2, 101)
    flanges = (
        ("Top flange (y = +h_m/2)", y_mid, "top_flange"),
        ("Bottom flange (y = −h_m/2)", -y_mid, "bottom_flange"),
    )
    fig, axes = _figure(1, 2, figsize=(8, 4.4), sharey=True)
    for ax, (title, y, field) in zip(axes, flanges, strict=True):
        ax.axvspan(-half_web, half_web, color=BAND, linewidth=0, zorder=0)
        ax.axhline(0, color=AXIS, linewidth=0.8)
        ax.plot(
            z,
            warping_stress_at(params, x, y, z),
            color=INK,
            linewidth=1,
            label="E·ω·φ'' (Vlasov target)",
        )
        ax.plot(
            z,
            warping_stress_at(params, x, y, z, a.end_corrected_torsion_constant),
            **END_CORRECTED,
            label="end-corrected J (information)",
        )
        for level in levels:
            series = level.series
            ax.plot(
                getattr(series, f"{field}_z"),
                getattr(series, f"{field}_sxx"),
                **_level_marker_style(series),
            )
        ax.text(0, 0.02, "web", transform=ax.get_xaxis_transform(), ha="center", color=INK)
        ax.set_title(title)
        ax.set_xlabel("z across the flange width (mm)")
    axes[0].set_ylabel("σ_xx at x = L/4 (MPa)")
    axes[0].legend(loc="lower left")
    fig.savefig(path)

    fine = levels[-1]
    tips = fine.result.flange_tip_warping_stresses
    errors = fine.result.warping_stress_errors
    return (
        "Nodal σ_xx across the width of the top and the bottom flange at x = L/4, the mean "
        "through the flange thickness at each z, for each mesh level, against the thin-walled "
        f"warping stress σ_w = −E·y·z·φ''(L/4) on the flange mid-planes (y = ±h_m/2). It is "
        "linear across each flange, zero over the web (shaded) and opposite in sign on the two "
        "edges of a flange and on the two flanges: the + − − + pattern at the four flange tips. "
        "The torque turns the top flange towards +z, so its −z edge is in tension and its +z "
        "edge in compression. At the flange tips the "
        f"{fine.result.mesh_level.name} level reads {tips[0]:+.2f} and {tips[1]:+.2f} MPa on the "
        f"top flange, {errors[0]:+.2f} % against ±{a.quarter_span_warping_stress:.2f} MPa, "
        "the verdict values of REPORT.md. The levels agree to within a few tenths of a MPa. "
        "The dotted line (information) uses the end-corrected J, with "
        f"±{a.end_corrected_quarter_span_warping_stress:.2f} MPa at the tips."
    )


def flange_tip_stress_figure(
    levels: Sequence[MeshLevelResults], params: BenchmarkParameters, path: Path
) -> str:
    a = analytical_solution(params)
    length = params.length
    y, z = a.flange_mid_plane_distance / 2, -params.section.flange_width / 2
    j_corrected = a.end_corrected_torsion_constant
    x = np.linspace(0, length, 301)
    vlasov = warping_stress_at(params, x, y, z)
    corrected = warping_stress_at(params, x, y, z, j_corrected)
    fig, (along, difference) = _figure(2, 1, figsize=(8, 6.4), sharex=True, height_ratios=(3, 2))

    for ax in (along, difference):
        ax.axvline(length / 4, color=SECONDARY_INK, linewidth=0.8, linestyle="--")
    along.text(
        length / 4,
        0.98,
        " x = L/4, verdict",
        transform=along.get_xaxis_transform(),
        va="top",
        color=SECONDARY_INK,
    )
    along.plot(x, vlasov, color=INK, linewidth=1, label="E·ω·φ''(x), Vlasov")
    along.plot(x, corrected, **END_CORRECTED, label="end-corrected J (information)")
    difference.axhline(0, color=INK, linewidth=1)
    difference.plot(x, corrected - vlasov, **END_CORRECTED)
    for level in levels:
        s = level.series
        style = _level_line_style(s)
        along.plot(s.flange_tip_x, s.flange_tip_sxx, **style)
        difference.plot(
            s.flange_tip_x,
            s.flange_tip_sxx - warping_stress_at(params, s.flange_tip_x, y, z),
            **style,
        )

    along.set_title("σ_xx along the top flange tip at z = −b/2")
    along.set_ylabel("σ_xx (MPa)")
    along.legend(loc="upper right")
    difference.set_title("Difference from Vlasov", fontsize=9)
    difference.set_ylabel("σ_xx − E·ω·φ'' (MPa)")
    difference.set_xlabel("x from the root face (mm)")
    fig.savefig(path)

    roots = " → ".join(f"{level.series.flange_tip_sxx[0]:.1f}" for level in levels)
    names = " → ".join(level.result.mesh_level.name for level in levels)
    fine = levels[-1].series
    station_2500 = np.isclose(fine.flange_tip_x, 2500.0)
    zone = tip_zone(levels[-1].result, params)
    return (
        "Nodal σ_xx along the top flange-tip edge at z = −b/2, the mean through the flange "
        "thickness at each x station, for each mesh level, against the Vlasov warping stress "
        f"E·ω·φ''(x) with ω = h_m·b/4. It is largest at the root, where the fixed face "
        f"restrains warping, and decays along the beam with the length 1/λ = "
        f"{1 / a.torsion_parameter:.0f} mm. Three zones show:\n\n"
        "- **Root.** At the root face itself the FE σ_xx at this flange tip "
        f"({roots} MPa, {names}; not the report's root peak von Mises, the largest over the "
        "whole root face) grows with refinement beyond the thin-walled "
        f"{a.root_warping_stress:.2f} MPa: the fixed face is singular at its edges, so the root "
        "value is information only.\n"
        "- **Middle.** Between the root zone and x ≈ L/3 the FE curves follow Vlasov a few % "
        "above it, as in figure 2; at x = L/4 (dashed) this is the verdict value. The dotted "
        "end-corrected curve (information) is closer.\n"
        "- **Towards the tip.** Instead of falling towards zero, the FE stress levels off at "
        f"{zone.plateau_min:.0f}–{zone.plateau_max:.0f} MPa between x = "
        f"{PLATEAU_RANGE[0]:.0f} and {PLATEAU_RANGE[1]:.0f} mm, where Vlasov drops to a few MPa "
        f"({warping_stress_at(params, 2500.0, y, z):.1f} MPa at x = 2500, FE "
        f"{fine.flange_tip_sxx[station_2500][0]:.1f}), and it returns near zero only at the "
        "tip face, which is free to warp. All three mesh levels agree, so it is not a "
        "discretisation error. The likely cause, not proven, is the load introduction: the "
        "distributing *COUPLING spreads the torque in proportion to the distance from the "
        "axis, which puts most of it into the flanges as lateral shear, while Vlasov carries "
        "it almost entirely as St-Venant shear at a free tip. In an open section that "
        "difference is not confined to a short zone but decays over a length of the order of "
        "1/λ: on the "
        f"{levels[-1].result.mesh_level.name} level the FE stress is more than "
        f"{ONSET_MARGIN * 100:g} % above the end-corrected curve from x = {zone.onset_x:.0f} mm "
        f"on, {length - zone.onset_x:.0f} mm from the tip. x = L/4 is clear of it: there the FE "
        f"stress is {zone.quarter_span_vs_end_corrected:+.2f} % from the end-corrected curve. "
        f"Follow-up: {FOLLOW_UP}."
    )


def convergence_figure(
    levels: Sequence[MeshLevelResults], params: BenchmarkParameters, path: Path
) -> str:
    a = analytical_solution(params)
    points = [level.series.convergence for level in levels]
    labels = [level.result.mesh_level.label for level in levels]
    corrected_twist = (a.end_corrected_tip_twist / a.tip_twist - 1) * 100
    corrected_stress = (
        a.end_corrected_quarter_span_warping_stress / a.quarter_span_warping_stress - 1
    ) * 100
    quantities = (
        (
            "Tip twist φ(L)",
            "o",
            BLUE,
            [p.tip_twist_error for p in points],
            TIP_TWIST_TOLERANCE_PERCENT,
            corrected_twist,
        ),
        (
            "Flange-tip σ_w at x = L/4",
            "s",
            ORANGE,
            [p.warping_stress_error for p in points],
            WARPING_STRESS_TOLERANCE_PERCENT,
            corrected_stress,
        ),
    )
    positions = np.arange(len(points))
    fig, axes = _figure(1, 2, figsize=(8, 4.4))
    for ax, (label, marker, color, errors, limit, corrected) in zip(axes, quantities, strict=True):
        ax.axhline(limit, color=SECONDARY_INK, linewidth=1, linestyle="--")
        ax.text(-0.2, limit, f"{limit:g} % pass limit", va="bottom", color=SECONDARY_INK)
        ax.axhline(corrected, **END_CORRECTED)
        ax.text(
            -0.2,
            corrected,
            f"end-corrected J: {corrected:+.2f} % (information)",
            va="top" if corrected < min(errors) else "bottom",
            color=SECONDARY_INK,
        )
        ax.plot(positions, errors, marker=marker, color=color, markersize=7)
        for position, error in zip(positions, errors, strict=True):
            ax.annotate(
                f"{error:+.2f} %",
                (position, error),
                xytext=(0, 8),
                textcoords="offset points",
                ha="center",
                color=INK,
            )
        ax.set_xticks(positions, labels)
        ax.set_xlim(-0.3, len(points) - 0.7)
        ax.set_ylim(0, limit + 1)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:+g}"))
        ax.set_title(label)
    axes[0].set_ylabel("signed error against the thin-walled target (%)")
    fig.supxlabel(
        "mesh level: elements through the flange thickness / along the web height / along the "
        "length",
        color=SECONDARY_INK,
        fontsize=9,
    )
    fig.savefig(path)

    twists = " → ".join(f"{p.tip_twist_error:+.2f}" for p in points)
    stresses = " → ".join(f"{p.warping_stress_error:+.2f}" for p in points)
    return (
        "Signed errors of the two verdict quantities against their thin-walled targets, one "
        "point per mesh level; each level halves the element length along x "
        f"({' → '.join(f'{p.element_length:g}' for p in points)} mm). The tip twist error runs "
        f"{twists} % and the flange-tip warping stress error at L/4 {stresses} % (the mean of "
        "the four flange tips, which agree by symmetry). Both sit inside their pass limits "
        "(dashed) from the coarse level on, and both grow slightly with refinement instead of "
        "shrinking towards zero: the coarse mesh is a little stiff in torsion, and the FE "
        "converges towards the solid section's own answer, not towards thin-walled theory. The "
        "dotted lines (information) mark where Vlasov with the end-corrected J lies against the "
        f"targets, {corrected_twist:+.2f} % and {corrected_stress:+.2f} %: the end correction "
        "accounts for most of the gap, and REPORT.md lists the other sources."
    )


FIGURES = (
    (1, "twist", "Twist along the beam", twist_figure),
    (2, "stress-across-flanges", "σ_xx across the flanges at x = L/4", flange_width_stress_figure),
    (3, "flange-tip-stress", "Warping stress along the flange tip", flange_tip_stress_figure),
    (4, "convergence", "Convergence over the mesh levels", convergence_figure),
    (5, "stress-render", "σ_xx on the twisted beam", stress_figure),
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
        "markersize": MARKER_SIZES[series.mesh_level.name],
    }


def _figure_section(number: int, title: str, name: str, caption: str) -> str:
    return (
        f"## Figure {number}. {title}\n\n![Figure {number}: {title}](figures/{name})\n\n{caption}\n"
    )


def _figures_page(sections: list[str]) -> str:
    header = [
        "# IPE 200 cantilever in torsion benchmark figures",
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
