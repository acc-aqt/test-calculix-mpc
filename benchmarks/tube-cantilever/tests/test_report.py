import pytest

from analytical import analytical_solution
from benchmark_parameters import CHS168_CANTILEVER, COARSE, FINE, MEDIUM
from report import Verdict, observed_order, render_report, verdict
from runner import BenchmarkResult

# Targets for CHS 168.3 x 8 (see test_analytical.py): Timoshenko with Cowper kappa 1.28126 mm,
# midspan stress 32.4335 MPa.
DEFLECTION_TARGET = 1.28126
STRESS_TARGET = 32.4335


def result(level, deflection_ratio=1.0, top_ratio=1.0, bottom_ratio=1.0, root_peak=80.0):
    """A result record whose FE values are the given ratios of the targets."""
    return BenchmarkResult(
        mesh_level=level,
        element_count=1,
        node_count=1,
        reference_node_uy=-DEFLECTION_TARGET * deflection_ratio,
        tip_face_mean_uy=-DEFLECTION_TARGET * deflection_ratio,
        midspan_top_fitted_sxx=STRESS_TARGET * top_ratio,
        midspan_bottom_fitted_sxx=-STRESS_TARGET * bottom_ratio,
        top_fibre_sxx=STRESS_TARGET * top_ratio,
        bottom_fibre_sxx=-STRESS_TARGET * bottom_ratio,
        root_peak_von_mises=root_peak,
        analytical=analytical_solution(CHS168_CANTILEVER),
    )


def converging(fine_deflection=1.0, fine_top=1.001, fine_bottom=1.001):
    """Coarse, medium and fine records whose stress errors shrink +1.4 → +0.25 % → fine."""
    return [
        result(COARSE, 1.0008, 1.014, 1.014),
        result(MEDIUM, 0.9999, 1.0025, 1.0025),
        result(FINE, fine_deflection, fine_top, fine_bottom),
    ]


def test_converging_levels_with_fine_within_one_percent_pass():
    assert verdict(converging(fine_deflection=0.991, fine_top=0.999, fine_bottom=0.9995)) is (
        Verdict.PASS
    )


def test_fine_deflection_off_by_more_than_one_percent_fails():
    assert verdict(converging(fine_deflection=1.011)) is Verdict.FAIL
    assert verdict(converging(fine_deflection=0.989)) is Verdict.FAIL


def test_fine_fitted_stress_off_by_more_than_one_percent_at_either_fibre_fails():
    stalled = result(MEDIUM, 1.0, 1.02, 1.02)
    for fine in (result(FINE, top_ratio=1.011), result(FINE, bottom_ratio=0.989)):
        assert verdict([result(COARSE, 1.0, 1.05, 1.05), stalled, fine]) is Verdict.FAIL


def test_stress_error_not_shrinking_from_coarse_to_medium_fails():
    levels = [result(COARSE, 1.0, 1.002, 1.002), result(MEDIUM, 1.0, 1.003, 1.003)]
    assert verdict([*levels, result(FINE, 1.0, 1.001, 1.001)]) is Verdict.FAIL


def test_stress_error_not_shrinking_from_medium_to_fine_at_one_fibre_fails():
    assert verdict(converging(fine_top=1.001, fine_bottom=1.0025)) is Verdict.FAIL


def test_only_the_fine_level_decides_the_tolerance():
    coarse_far_off = result(COARSE, deflection_ratio=1.5, top_ratio=1.2, bottom_ratio=1.2)
    medium_off = result(MEDIUM, deflection_ratio=0.95, top_ratio=1.05, bottom_ratio=1.05)
    assert verdict([coarse_far_off, medium_off, result(FINE, 1.0, 1.001, 1.001)]) is Verdict.PASS


def test_deflection_error_need_not_shrink():
    # The deflection sits on its modelling floor from the medium level on.
    levels = converging(fine_deflection=0.99993)
    levels[1] = result(MEDIUM, 0.99991, 1.0025, 1.0025)
    assert verdict(levels) is Verdict.PASS


def test_root_peak_stress_never_affects_the_verdict():
    levels = converging()
    levels[2] = result(FINE, 1.0, 1.001, 1.001, root_peak=1e6)
    assert verdict(levels) is Verdict.PASS


def test_no_verdict_without_the_fine_level():
    assert verdict([result(COARSE), result(MEDIUM)]) is None


def test_no_verdict_when_a_coarser_level_is_missing_because_shrinking_needs_all_three():
    assert verdict([result(MEDIUM, 1.0, 1.0025, 1.0025), result(FINE)]) is None


def test_stress_errors_are_signed_so_a_flipped_fibre_sign_fails():
    flipped = result(FINE, top_ratio=-1.0, bottom_ratio=-1.0)
    assert flipped.midspan_top_stress_error == pytest.approx(-200)
    assert flipped.midspan_bottom_stress_error == pytest.approx(-200)
    assert flipped.top_fibre_stress_error == pytest.approx(-200)
    assert verdict([result(COARSE, 1.0, 3.5, 3.5), result(MEDIUM, 1.0, 2.5, 2.5), flipped]) is (
        Verdict.FAIL
    )


def test_observed_order_of_the_prototype_stress_errors():
    # ln((1.354 - 0.246) / (0.246 - 0.076)) / ln 2 = 2.70; single node: ln(3.80 / 0.88) / ln 2.
    assert observed_order([1.354, 0.246, 0.076]) == pytest.approx(2.704, abs=1e-3)
    assert observed_order([5.00, 1.20, 0.32]) == pytest.approx(2.111, abs=1e-3)


def test_observed_order_is_not_available_when_the_errors_do_not_fall_geometrically():
    # The prototype deflection crosses zero and then sits on its floor.
    assert observed_order([0.076, -0.009, -0.007]) is None
    assert observed_order([0.1, 0.05, 0.05]) is None


def test_observed_order_is_not_available_without_three_levels():
    assert observed_order([1.354, 0.246]) is None


def test_report_shows_the_verdict_targets_and_a_row_per_level():
    text = render_report(converging(), CHS168_CANTILEVER, "Version 2.24")
    assert "Version 2.24" in text
    assert "Verdict: **PASS**" in text
    assert "| κ (Cowper) | 0.5327 |" in text
    for target in ("1.22357", "1.28126", "1.28503", "32.4335"):
        assert target in text
    for level in ("| coarse |", "| medium |", "| fine |"):
        assert level in text


def test_report_shows_the_observed_order_and_n_a_when_it_is_not_defined():
    levels = [
        result(COARSE, 1.00076, 1.01354, 1.01354),
        result(MEDIUM, 0.99991, 1.00246, 1.00246),
        result(FINE, 0.99993, 1.00076, 1.00076),
    ]
    text = render_report(levels, CHS168_CANTILEVER, "Version 2.24")
    assert "| Deflection vs δ_T | n/a |" in text
    assert "| Midspan stress fit | 2.70 |" in text


def test_report_calls_the_deflection_floor_a_modelling_residual():
    text = render_report(converging(), CHS168_CANTILEVER, "Version 2.24")
    assert "modelling residual" in text


def test_partial_run_report_says_not_evaluated():
    text = render_report([result(COARSE)], CHS168_CANTILEVER, "Version 2.24")
    assert "not evaluated" in text


def test_report_links_to_the_figures_page():
    text = render_report(converging(), CHS168_CANTILEVER, "Version 2.24")
    assert "](FIGURES.md)" in text
