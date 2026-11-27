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

from benchmark_parameters import LE10, MESH_LEVELS, BenchmarkParameters
from deck import C3D20, C3D20R, generate_deck
from figure_data import FigureSeries, MeshLevelResults, figure_series
from frd import read_frd
from palette import AXIS, BAND, BLUE, DARK_BLUE, GRID, INK, LIGHT_BLUE, ORANGE, SECONDARY_INK
from reference import target_stress_at_d
from renders import (
    boundary_conditions_figure,
    displacement_figure,
    mesh_figure,
    stress_figure,
)
from report import LOW_ORDER, TOLERANCE_PERCENT, observed_order, richardson_estimate
from runner import benchmark_result, result_files

HERE = Path(__file__).resolve().parent
LEVELS_BY_NAME = {level.name: level for level in MESH_LEVELS}

LEVEL_STYLES = {
    "coarse": {"color": LIGHT_BLUE, "marker": "o"},
    "medium": {"color": BLUE, "marker": "s"},
    "fine": {"color": DARK_BLUE, "marker": "^"},
}
TARGET = {"color": INK, "marker": "D", "markersize": 7, "linestyle": "none"}

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
    files = [
        result_files(level, args.work_dir, element_type)
        for level in levels
        for element_type in (C3D20R, C3D20)
    ]
    missing = [path for paths in files for path in paths if not path.is_file()]
    if missing:
        listed = "\n".join(f"  {path}" for path in missing)
        print(
            f"Missing solver output:\n{listed}\nRun benchmark.py first; no figures written.",
            file=sys.stderr,
        )
        return 1

    params = LE10
    results = []
    for level in levels:
        print(f"Reading mesh level {level.name} ...", flush=True)
        reduced, frd, deck = _read_level(level, params, args.work_dir, C3D20R)
        full_integration, _, _ = _read_level(level, params, args.work_dir, C3D20)
        series = figure_series(reduced, params, deck, frd, full_integration)
        results.append(MeshLevelResults(reduced, deck, frd, series))

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


def thickness_stress_figure(
    levels: Sequence[MeshLevelResults], params: BenchmarkParameters, path: Path
) -> str:
    target = target_stress_at_d()
    half = params.thickness / 2
    fig, ax = _figure(figsize=(6, 4.8))
    ax.axvline(0, color=AXIS, linewidth=0.8)
    for level in levels:
        s = level.series
        ax.plot(s.thickness_syy, s.thickness_z, **_level_style(s))
    ax.plot(
        target, half, **TARGET, clip_on=False, label=f"published σ_yy(D) = {_signed(target)} MPa"
    )
    ax.set_ylim(-half, half)
    ax.set_yticks(np.linspace(-half, half, 5))
    ax.set_title("σ_yy through the thickness at x = a_i, y = 0")
    ax.set_xlabel("σ_yy (MPa)")
    ax.set_ylabel("z (mm)")
    ax.legend(loc="lower left")
    fig.savefig(path)

    fine = levels[-1].series
    neutral = _zero_crossing(fine.thickness_syy, fine.thickness_z)
    names = " → ".join(level.result.mesh_level.name for level in levels)
    tops = " → ".join(_signed(level.series.thickness_syy[-1], 3) for level in levels)
    bottoms = " → ".join(_signed(level.series.thickness_syy[0], 3) for level in levels)
    return (
        "Nodal σ_yy through the thickness at the hole edge on the x axis (x = a_i, y = 0), "
        f"from the bottom face (z = −{half:g} mm) to point D on the loaded top face "
        f"(z = +{half:g} mm), one marker per node, for each mesh level. The plate bends over "
        "the hole: σ_yy is compressive at the top and tensile at the bottom. At D it is "
        f"{tops} MPa ({names}) against the published {_signed(target)} MPa (diamond), at the "
        f"bottom face {bottoms} MPa. On the {fine.mesh_level.name} level σ_yy changes sign "
        f"at z = {_signed(neutral, 0)} mm."
    )


def convergence_figure(
    levels: Sequence[MeshLevelResults], params: BenchmarkParameters, path: Path
) -> str:
    target = target_stress_at_d()
    band = abs(target) * TOLERANCE_PERCENT / 100
    points = [level.series.convergence for level in levels]
    positions = np.arange(len(points))
    reduced = [p.stress_yy_at_d for p in points]
    full = [p.full_integration_stress_yy_at_d for p in points]
    all_three = len(points) == len(MESH_LEVELS)
    estimate = richardson_estimate(*reduced) if all_three else None
    order = observed_order(*reduced) if all_three else None
    right = len(points) - 0.6

    fig, ax = _figure(figsize=(7, 4.6))
    ax.axhspan(target - band, target + band, color=BAND, linewidth=0, zorder=0)
    ax.axhline(target, color=INK, linewidth=1)
    ax.text(
        right,
        target + band,
        f"published {_signed(target)} MPa ± {TOLERANCE_PERCENT:g} % (pass band) ",
        ha="right",
        va="top",
        color=SECONDARY_INK,
    )
    if estimate is not None:
        ax.axhline(estimate, color=SECONDARY_INK, linewidth=0.8, linestyle=":")
        ax.text(
            right,
            estimate,
            f"Richardson estimate {_signed(estimate, 3)} MPa, p = {order:.2f} (information) ",
            ha="right",
            va="bottom",
            color=SECONDARY_INK,
        )
    for values, label, color, marker in (
        (reduced, "C3D20R (verdict on the fine level)", BLUE, "o"),
        (full, "C3D20 (information)", ORANGE, "s"),
    ):
        ax.plot(positions, values, color=color, marker=marker, markersize=7, label=label)
        ax.annotate(
            _signed(values[-1], 3),
            (positions[-1], values[-1]),
            xytext=(10, 0),
            textcoords="offset points",
            va="center",
            color=INK,
        )
    ax.set_xticks(positions, [p.mesh_level.label for p in points])
    ax.set_xlim(-0.3, right)
    ax.set_ylim(target - 1.8 * band, target + 1.8 * band)
    ax.set_title("σ_yy(D) over the mesh levels")
    ax.set_ylabel("σ_yy(D) (MPa)")
    ax.set_xlabel("mesh level: elements around × across × through the thickness")
    ax.legend(loc="upper left")
    fig.savefig(path)

    def run(values: list[float], errors: list[float]) -> str:
        return " → ".join(
            f"{_signed(v, 3)} ({_signed(e, 2, plus=True)} %)"
            for v, e in zip(values, errors, strict=True)
        )

    caption = (
        "Nodal σ_yy(D) at each mesh level for C3D20R, which decides the verdict on the fine "
        "level, and for C3D20 (full integration, information only), against the published "
        f"{_signed(target)} MPa and its ±{TOLERANCE_PERCENT:g} % pass band (shaded). C3D20R "
        f"runs {run(reduced, [p.stress_yy_at_d_error for p in points])} MPa and C3D20 "
        f"{run(full, [p.full_integration_stress_yy_at_d_error for p in points])} MPa."
    )
    if estimate is None:
        return caption + " The Richardson estimate needs the coarse, medium and fine levels."
    caption += (
        " The dotted line is the Richardson estimate from the three C3D20R levels, "
        f"{_signed(estimate, 3)} MPa with the observed order p = {order:.2f} (information)."
    )
    if order < LOW_ORDER:
        caption += (
            " That order is low, so the sequence is not yet in its asymptotic range and the "
            "estimate is not a reliable limit (see REPORT.md)."
        )
    return caption


def hole_edge_stress_figure(
    levels: Sequence[MeshLevelResults], params: BenchmarkParameters, path: Path
) -> str:
    target = target_stress_at_d()
    fig, ax = _figure(figsize=(7, 4.4))
    ax.axhline(0, color=AXIS, linewidth=0.8)
    for level in levels:
        s = level.series
        ax.plot(s.hole_edge_theta, s.hole_edge_syy, **_level_style(s))
    ax.plot(0, target, **TARGET, clip_on=False, label=f"published σ_yy(D) = {_signed(target)} MPa")
    _hole_edge_axis(ax)
    ax.set_title(f"σ_yy along the hole edge on the top face (z = +{params.thickness / 2:g} mm)")
    ax.set_ylabel("σ_yy (MPa)")
    ax.legend(loc="lower right")
    fig.savefig(path)

    fine = levels[-1].series
    return (
        "Nodal σ_yy along the top-face hole edge from D (θ = 0°, on the x axis) to A "
        "(θ = 90°, on the y axis), against the parametric angle θ of the hole ellipse, "
        "(a_i cos θ, b_i sin θ), one marker per node, for each mesh level. At D the hole edge "
        "runs along y, so σ_yy is the hoop stress there, the verdict quantity (diamond: the "
        f"published {_signed(target)} MPa). Towards A the edge turns to run along x, so σ_yy "
        "becomes the stress normal to the traction-free hole face and falls to about zero "
        f"({_signed(fine.hole_edge_syy[-1], 3)} MPa at A on the {fine.mesh_level.name} level)."
    )


def hole_edge_displacement_figure(
    levels: Sequence[MeshLevelResults], params: BenchmarkParameters, path: Path
) -> str:
    fig, ax = _figure(figsize=(7, 4.4))
    for level in levels:
        s = level.series
        ax.plot(s.hole_edge_theta, s.hole_edge_uz, **_level_style(s))
    _hole_edge_axis(ax)
    ax.set_title(f"u_z along the hole edge on the top face (z = +{params.thickness / 2:g} mm)")
    ax.set_ylabel("u_z (mm), negative is downwards")
    ax.legend(loc="upper right")
    fig.savefig(path)

    names = " → ".join(level.result.mesh_level.name for level in levels)
    at_d = " → ".join(_signed(level.series.hole_edge_uz[0], 4) for level in levels)
    at_a = " → ".join(_signed(level.series.hole_edge_uz[-1], 4) for level in levels)
    return (
        "Nodal out-of-plane displacement u_z along the top-face hole edge from D (θ = 0°) to "
        "A (θ = 90°), for each mesh level. The plate rests on line EE′ at its outer edge, so "
        "the pressure pushes the whole hole edge down. u_z is "
        f"{at_d} mm at D and {at_a} mm at A ({names})."
    )


FIGURES = (
    (1, "mesh", "Mesh levels", mesh_figure),
    (2, "boundary-conditions", "Supports and load", boundary_conditions_figure),
    (3, "stress-through-thickness", "σ_yy through the thickness at D", thickness_stress_figure),
    (4, "convergence", "Convergence of σ_yy(D)", convergence_figure),
    (5, "stress-render", "σ_yy on the deformed plate", stress_figure),
    (6, "hole-edge-stress", "σ_yy along the hole edge", hole_edge_stress_figure),
    (7, "displacement-render", "u_z on the deformed plate", displacement_figure),
    (8, "hole-edge-displacement", "u_z along the hole edge", hole_edge_displacement_figure),
)
"""(number, file slug, title, draw). draw(levels, params, path) writes the PNG and returns the
caption."""


def _hole_edge_axis(ax) -> None:
    ax.set_xlim(0, 90)
    ticks = range(0, 91, 15)
    names = {0: "\nD", 90: "\nA"}
    ax.set_xticks(ticks, [f"{theta}°{names.get(theta, '')}" for theta in ticks])
    ax.set_xlabel("parametric angle θ on the hole edge")


def _zero_crossing(values: np.ndarray, positions: np.ndarray) -> float:
    n = int(np.flatnonzero(np.diff(np.sign(values)))[0])
    return float(np.interp(0.0, values[[n + 1, n]], positions[[n + 1, n]]))


def _figure(figsize: tuple[float, float]):
    fig = Figure(figsize=figsize, layout="constrained")
    return fig, fig.subplots()


def _level_style(series: FigureSeries) -> dict:
    return {**LEVEL_STYLES[series.mesh_level.name], "label": series.mesh_level.label}


def _signed(value: float, digits: int | None = None, plus: bool = False) -> str:
    sign = "+" if plus else ""
    text = f"{value:{sign}g}" if digits is None else f"{value:{sign}.{digits}f}"
    return text.replace("-", "−")


def _read_level(level, params, work_dir, element_type):
    frd_path, dat_path = result_files(level, work_dir, element_type)
    frd = read_frd(frd_path)
    deck = generate_deck(params, level, element_type)
    return benchmark_result(level, element_type, params, deck, frd, dat_path), frd, deck


def _figure_section(number: int, title: str, name: str, caption: str) -> str:
    return (
        f"## Figure {number}. {title}\n\n![Figure {number}: {title}](figures/{name})\n\n{caption}\n"
    )


def _figures_page(sections: list[str]) -> str:
    header = [
        "# NAFEMS LE10 thick plate benchmark figures",
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
