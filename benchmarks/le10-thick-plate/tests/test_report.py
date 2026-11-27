import pytest
from records import levels, result

from benchmark_parameters import COARSE, FINE, LE10, MEDIUM
from deck import C3D20
from report import Verdict, render_report, richardson_estimate, verdict


def test_richardson_recovers_the_limit_of_a_second_order_sequence():
    # -5 + 0.4 / 4**n for n = 0, 1, 2: errors 0.4, 0.1, 0.025 halve the mesh size each time.
    assert richardson_estimate(-4.6, -4.9, -4.975) == pytest.approx(-5.0)


def test_richardson_recovers_the_limit_of_a_first_order_sequence_approached_from_below():
    assert richardson_estimate(-6.0, -5.5, -5.25) == pytest.approx(-5.0)


@pytest.mark.parametrize("values", [(-5.4, -5.3, -5.4), (-5.4, -5.3, -5.1), (-5.4, -5.3, -5.3)])
def test_richardson_is_not_available_when_the_differences_do_not_shrink_geometrically(values):
    assert richardson_estimate(*values) is None


def test_report_states_solver_version_and_that_the_verdict_is_not_evaluated():
    text = render_report([result(COARSE)], LE10, "Version 2.24")
    assert "Version 2.24" in text
    assert "not evaluated" in text


def test_report_lists_the_le10_parameters():
    text = render_report([result(COARSE)], LE10, "Version 2.24")
    assert "| Inner ellipse (hole edge) | a_i = 2000, b_i = 1000 mm |" in text
    assert "| Outer ellipse | a_o = 3250, b_o = 2750 mm |" in text
    assert "| Thickness | t = 600 mm, z from −300 to +300 mm |" in text
    assert "| Material | E = 210000 MPa, ν = 0.3 |" in text
    assert "| Load | p = 1 MPa on the top face (z = +300 mm) |" in text


def test_report_states_the_published_target_and_its_provenance():
    text = render_report([result(COARSE)], LE10, "Version 2.24")
    assert "| σ_yy(D), published (target) | −5.38 MPa |" in text
    assert "TNSB Rev. 3" in text and "not consulted" in text
    assert "0004" in text


def test_level_row_shows_sigma_yy_at_d_its_signed_error_and_the_integration_point_value():
    text = render_report([result(COARSE, stress_ratio=1.05)], LE10, "Version 2.24")
    # 1.05 x -5.38 = -5.649 MPa, +5.00 % against -5.38 MPa.
    assert "| coarse 6×4×2 | 48 | 349 | -5.649 | +5.00 | -3.820 |" in text


def test_report_shows_the_stress_tensor_and_von_mises_at_d():
    text = render_report([result(COARSE)], LE10, "Version 2.24")
    assert "| coarse | -0.357 | -5.380 | -1.085 | 0.060 | -0.019 | -0.054 | 4.704 |" in text


@pytest.mark.parametrize("fine_ratio", [1.0299, 0.9701])
def test_fine_sigma_yy_at_d_just_inside_three_percent_passes(fine_ratio):
    assert verdict(levels(1.5, 1.2, fine_ratio)) is Verdict.PASS


@pytest.mark.parametrize("fine_ratio", [1.0301, 0.9699])
def test_fine_sigma_yy_at_d_just_outside_three_percent_fails(fine_ratio):
    assert verdict(levels(1.5, 1.2, fine_ratio)) is Verdict.FAIL


def test_a_flipped_sign_fails():
    flipped = levels(-1.0, -1.0, -1.0)
    assert flipped[2].stress_yy_at_d_error == pytest.approx(-200)
    assert verdict(flipped) is Verdict.FAIL


@pytest.mark.parametrize(
    "ratios",
    [(1.02, 1.01, 1.0), (1.01, 1.0, 1.02), (1.0, 1.02, 1.0)],
    ids=["growing steps", "diverging", "equal steps"],
)
def test_a_non_converging_sequence_fails_even_with_the_fine_level_on_target(ratios):
    assert verdict(levels(*ratios)) is Verdict.FAIL


def test_only_the_fine_level_decides_the_tolerance():
    assert verdict(levels(1.5, 1.2, 1.0)) is Verdict.PASS
    assert verdict(levels(1.0, 1.02, 1.035)) is Verdict.FAIL


def test_no_fine_level_gives_no_verdict():
    assert verdict([result(COARSE), result(MEDIUM)]) is None
    assert verdict([result(COARSE)]) is None


def test_fine_level_without_coarse_and_medium_gives_no_verdict():
    assert verdict([result(FINE)]) is None


def test_information_values_never_count():
    far_off = [
        result(level, ratio, sxx=1e6, integration_point_stress_yy=1e6)
        for level, ratio in ((COARSE, 1.5), (MEDIUM, 1.2), (FINE, 1.0))
    ]
    assert verdict(far_off) is Verdict.PASS


def test_report_shows_the_verdict_with_its_rule():
    text = render_report(levels(1.5, 1.2, 1.0), LE10, "Version 2.24")
    assert "- Verdict: **PASS**" in text
    assert "## Verdict" in text
    assert "±3 %" in text and "|fine − medium| < |medium − coarse|" in text


def test_report_shows_fail_when_the_fine_level_fails():
    text = render_report(levels(1.5, 1.2, 1.1), LE10, "Version 2.24")
    assert "- Verdict: **FAIL**" in text


def test_report_has_a_convergence_table_row_per_level():
    text = render_report(levels(1.5, 1.2, 1.0), LE10, "Version 2.24")
    assert "## Convergence" in text
    assert "| coarse 6×4×2 | 48 | 349 | -8.070 | +50.00 |" in text
    assert "| medium 12×8×4 | 48 | 349 | -6.456 | +20.00 |" in text
    assert "| fine 24×16×8 | 48 | 349 | -5.380 |" in text


def test_report_shows_the_richardson_estimate_and_its_error():
    # Steps of 0.04 and 0.02 of the target down to a fine ratio of 1.01 extrapolate to 0.99:
    # 0.99 x -5.38 = -5.326 MPa, -1.00 %.
    text = render_report(levels(1.07, 1.03, 1.01), LE10, "Version 2.24")
    assert "| Richardson estimate (information) | −5.326 MPa | −1.00 % |" in text


def flagged(text):
    return "**Flagged**" in text


@pytest.mark.parametrize(
    ("limit_ratio", "is_flagged"),
    [(1.0201, True), (1.0199, False), (0.9799, True), (0.9801, False)],
)
def test_richardson_flag_appears_exactly_when_it_is_more_than_two_percent_off(
    limit_ratio, is_flagged
):
    # Steps of 0.02 and 0.01 of the target extrapolate to limit_ratio x the target.
    sequence = levels(limit_ratio + 0.04, limit_ratio + 0.02, limit_ratio + 0.01)
    assert flagged(render_report(sequence, LE10, "Version 2.24")) is is_flagged


def test_richardson_flag_does_not_change_the_verdict():
    # Steps of 0.008 and 0.004 down to a fine ratio of 1.029 extrapolate to 1.025.
    text = render_report(levels(1.041, 1.033, 1.029), LE10, "Version 2.24")
    assert flagged(text)
    assert "- Verdict: **PASS**" in text


@pytest.mark.parametrize(
    "results", [[result(COARSE)], levels(1.0, 1.02, 1.0)], ids=["coarse only", "oscillating"]
)
def test_richardson_estimate_is_not_available_without_three_converging_levels(results):
    text = render_report(results, LE10, "Version 2.24")
    assert "| Richardson estimate (information) | not available | – |" in text
    assert not flagged(text)


def test_report_links_the_figures_page():
    text = render_report([result(COARSE)], LE10, "Version 2.24")
    assert "- Figures: [FIGURES.md](FIGURES.md), generated by `python plots.py`" in text


def test_c3d20_rows_sit_beside_the_c3d20r_rows_for_information():
    results = [result(COARSE, 1.05), result(COARSE, 1.10, element_type=C3D20)]
    text = render_report(results, LE10, "Version 2.24")
    # C3D20R -5.649 MPa; C3D20 1.10 x -5.38 = -5.918 MPa, +10.00 %.
    assert "| coarse 6×4×2 | -5.649 | -5.918 | +10.00 | -3.820 |" in text
    assert "C3D20 (information)" in text


def c3d20_levels(*ratios):
    return [
        result(level, ratio, element_type=C3D20)
        for level, ratio in zip((COARSE, MEDIUM, FINE), ratios, strict=True)
    ]


def test_c3d20_values_never_count():
    reduced = levels(1.02, 1.005, 1.0)
    far_off = c3d20_levels(2.0, 2.0, 2.0)
    with_c3d20 = render_report(reduced + far_off, LE10, "Version 2.24")
    without = render_report(reduced, LE10, "Version 2.24")

    def counted(text):
        lines = text.splitlines()
        verdict_lines = [line for line in lines if line.startswith("- Verdict")]
        start = lines.index("## Convergence") + 1
        end = next(n for n in range(start, len(lines)) if lines[n].startswith("## "))
        return verdict_lines, lines[start:end]

    assert counted(with_c3d20) == counted(without)
    assert verdict(reduced + far_off) is Verdict.PASS
    assert verdict(levels(1.5, 1.2, 1.1) + c3d20_levels(1.5, 1.2, 1.0)) is Verdict.FAIL


def test_c3d20_levels_alone_give_no_verdict():
    assert verdict(c3d20_levels(1.5, 1.2, 1.0)) is None
    assert verdict([result(COARSE, 1.5), result(MEDIUM, 1.2), *c3d20_levels(1.5, 1.2, 1.0)]) is None


def test_report_says_a_low_observed_order_makes_the_richardson_estimate_unreliable():
    # Prototype steps 0.037 and 0.025 MPa: p = ln(0.037 / 0.025) / ln 2 = 0.57.
    text = render_report(levels(5.424 / 5.38, 5.387 / 5.38, 5.362 / 5.38), LE10, "V")
    assert "| Observed order p (information) | 0.57 | – |" in text
    assert "p = 0.57 is low" in text and "not a reliable limit" in text


def test_report_does_not_call_a_second_order_richardson_estimate_unreliable():
    text = render_report(levels(1.05, 1.0125, 1.003125), LE10, "V")
    assert "| Observed order p (information) | 2.00 | – |" in text
    assert "not a reliable limit" not in text
