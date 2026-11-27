import pytest

from analytical import analytical_solution
from benchmark_parameters import COARSE, FINE, IPE200_CANTILEVER, MEDIUM
from report import Verdict, verdict
from runner import BenchmarkResult

# Targets for the no-fillet IPE 200 (see test_analytical.py): Timoshenko 23.5677 mm, 81.2748 MPa.
DEFLECTION_TARGET = 23.5677
STRESS_TARGET = 81.2748


def result(level, deflection_ratio=1.0, top_ratio=1.0, bottom_ratio=1.0, root_peak=170.0):
    """A result record whose FE values are the given ratios of the targets."""
    return BenchmarkResult(
        mesh_level=level,
        element_count=1,
        node_count=1,
        reference_node_uy=-DEFLECTION_TARGET * deflection_ratio,
        web_centreline_tip_uy=-DEFLECTION_TARGET * deflection_ratio,
        midspan_top_sxx_width_mean=STRESS_TARGET * top_ratio,
        midspan_bottom_sxx_width_mean=-STRESS_TARGET * bottom_ratio,
        root_peak_von_mises=root_peak,
        analytical=analytical_solution(IPE200_CANTILEVER),
    )


def test_fine_mesh_within_two_percent_everywhere_passes():
    assert verdict([result(FINE, 1.019, 0.981, 1.019)]) is Verdict.PASS


def test_fine_mesh_deflection_off_by_more_than_two_percent_fails():
    assert verdict([result(FINE, deflection_ratio=1.021)]) is Verdict.FAIL
    assert verdict([result(FINE, deflection_ratio=0.979)]) is Verdict.FAIL


def test_fine_mesh_stress_off_by_more_than_two_percent_at_either_flange_fails():
    assert verdict([result(FINE, top_ratio=1.021)]) is Verdict.FAIL
    assert verdict([result(FINE, bottom_ratio=0.979)]) is Verdict.FAIL


def test_only_the_fine_mesh_decides_the_verdict():
    coarse_far_off = result(COARSE, deflection_ratio=1.5, top_ratio=0.5)
    assert verdict([coarse_far_off, result(MEDIUM), result(FINE)]) is Verdict.PASS


def test_root_peak_stress_never_affects_the_verdict():
    assert verdict([result(FINE, root_peak=1e6)]) is Verdict.PASS


def test_no_verdict_without_the_fine_mesh():
    assert verdict([result(COARSE), result(MEDIUM)]) is None


def test_stress_errors_are_signed_so_a_flipped_flange_sign_fails():
    flipped = result(FINE, top_ratio=-1.0, bottom_ratio=-1.0)
    assert flipped.midspan_top_stress_error == pytest.approx(-200)
    assert flipped.midspan_bottom_stress_error == pytest.approx(-200)
    assert verdict([flipped]) is Verdict.FAIL
