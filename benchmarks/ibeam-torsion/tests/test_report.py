import pytest

from analytical import analytical_solution
from benchmark_parameters import COARSE, FINE, IPE200_TORSION, MEDIUM
from report import Verdict, render_report, verdict
from runner import BenchmarkResult

VLASOV_TIP_TWIST = 0.26275
QUARTER_SPAN_WARPING_STRESS = 58.677
FLANGE_TIP_SIGNS = (1, -1, -1, 1)


def result(level, tip_ratio=1.0, stress_ratios=(1.0, 1.0, 1.0, 1.0), shear=69.1, root_peak=200.0):
    """A result record whose tip twist and flange-tip warping stresses are the given ratios of
    the Vlasov targets (top -z, top +z, bottom -z, bottom +z)."""
    tip = VLASOV_TIP_TWIST * tip_ratio
    return BenchmarkResult(
        mesh_level=level,
        element_count=420,
        node_count=3164,
        twist_curve=((0.0, 0.0), (1500.0, tip / 3), (3000.0, tip)),
        flange_tip_warping_stresses=tuple(
            sign * ratio * QUARTER_SPAN_WARPING_STRESS
            for sign, ratio in zip(FLANGE_TIP_SIGNS, stress_ratios, strict=True)
        ),
        midspan_st_venant_shear_stress=shear,
        root_peak_von_mises=root_peak,
        analytical=analytical_solution(IPE200_TORSION),
    )


def test_fine_level_within_the_tolerances_passes():
    assert verdict([result(FINE, 1.0799, (1.0499, 0.9501, 1.0499, 0.9501))]) is Verdict.PASS


@pytest.mark.parametrize("tip_ratio", [1.0801, 0.9199])
def test_fine_tip_twist_off_by_more_than_eight_percent_fails(tip_ratio):
    assert verdict([result(FINE, tip_ratio)]) is Verdict.FAIL


@pytest.mark.parametrize("tip", range(4))
@pytest.mark.parametrize("ratio", [1.0501, 0.9499])
def test_fine_warping_stress_off_by_more_than_five_percent_at_any_flange_tip_fails(tip, ratio):
    ratios = [1.0, 1.0, 1.0, 1.0]
    ratios[tip] = ratio
    assert verdict([result(FINE, stress_ratios=tuple(ratios))]) is Verdict.FAIL


@pytest.mark.parametrize("tip", range(4))
def test_a_flipped_flange_tip_sign_fails(tip):
    ratios = [1.0, 1.0, 1.0, 1.0]
    ratios[tip] = -1.0
    flipped = result(FINE, stress_ratios=tuple(ratios))
    assert flipped.warping_stress_errors[tip] == pytest.approx(-200)
    assert verdict([flipped]) is Verdict.FAIL


def test_only_the_fine_level_decides_the_verdict():
    far_off = result(COARSE, tip_ratio=1.5, stress_ratios=(0.5, -1.0, 1.0, 1.0))
    assert verdict([far_off, result(MEDIUM, 0.5), result(FINE)]) is Verdict.PASS
    assert verdict([result(COARSE), result(MEDIUM), result(FINE, 1.2)]) is Verdict.FAIL


def test_information_values_never_count():
    assert verdict([result(FINE, shear=1e6, root_peak=1e6)]) is Verdict.PASS
    assert verdict([result(FINE, shear=-1.0, root_peak=0.0)]) is Verdict.PASS


def test_no_fine_level_gives_no_verdict():
    assert verdict([result(COARSE), result(MEDIUM)]) is None


def test_report_states_solver_version_and_that_the_verdict_is_not_evaluated():
    text = render_report([result(COARSE)], IPE200_TORSION, "Version 2.24")
    assert "Version 2.24" in text
    assert "not evaluated" in text


def test_report_lists_parameters_and_targets():
    text = render_report([result(COARSE)], IPE200_TORSION, "Version 2.24")
    assert "T = 500000 N·mm about +x" in text
    assert "| J = (2·b·t_f³ + (h − 2t_f)·t_w³)/3 | 51654.2 mm⁴ |" in text
    assert "| φ(L), Vlasov (target) | 0.26275 rad |" in text
    assert "| φ_SV(L) = TL/(GJ) (information) | 0.35953 rad |" in text
    assert "58.68 MPa" in text and "148.84 MPa" in text and "69.10 MPa" in text


def test_report_lists_the_end_corrected_j_and_its_tip_twist_for_information():
    text = render_report([result(COARSE)], IPE200_TORSION, "Version 2.24")
    assert "| J, end-corrected (information) | 49255.3 mm⁴ |" in text
    assert "| φ(L), Vlasov with end-corrected J (information) | 0.27313 rad |" in text


def test_convergence_row_shows_twist_flange_tip_stresses_shear_and_root_peak_with_errors():
    record = result(COARSE, 1.05, (1.03, 1.03, 1.03, 1.03), shear=75.0, root_peak=300.0)
    text = render_report([record], IPE200_TORSION, "Version 2.24")
    # 1.05 x 0.26275 = 0.27589 rad; against phi_SV: 0.275888 / 0.359533 - 1 = -23.27 %.
    # 1.03 x 58.677 = 60.44 MPa; tau: 75.0 / 69.100 - 1 = +8.54 %.
    assert (
        "| coarse | 420 | 3164 | 0.27589 | +5.00 | -23.27 | +60.44 | +3.00 | -60.44 | +3.00 "
        "| -60.44 | +3.00 | +60.44 | +3.00 | 75.00 | +8.54 | 300.00 |"
    ) in text


def test_report_shows_the_verdict_with_its_rule_and_the_sign_pattern():
    text = render_report([result(COARSE), result(MEDIUM), result(FINE)], IPE200_TORSION, "V")
    assert "- Verdict: **PASS**" in text
    assert "## Verdict" in text
    assert "≤ 8 %" in text and "≤ 5 %" in text
    assert "+ − − +" in text


def test_report_shows_fail_when_the_fine_level_fails():
    text = render_report([result(FINE, 1.2)], IPE200_TORSION, "Version 2.24")
    assert "- Verdict: **FAIL**" in text


def test_report_explains_the_expected_gap_to_thin_walled_theory():
    text = render_report([result(COARSE)], IPE200_TORSION, "Version 2.24")
    for source in (
        "end correction",
        "web-flange junction",
        "warping shear deformation",
        "load-introduction zone",
    ):
        assert source in text
    assert "| σ_w(L/4), Vlasov with end-corrected J (information) | 61.37 MPa |" in text


def test_report_links_to_the_coupling_adr():
    text = render_report([result(COARSE)], IPE200_TORSION, "Version 2.24")
    assert "0003" in text
