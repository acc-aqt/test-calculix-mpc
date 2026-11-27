import numpy as np
import pytest

from analytical import twist_at, warping_stress_at
from benchmark_parameters import COARSE, IPE200_TORSION
from deck import generate_deck
from figure_data import figure_series
from frd import read_frd
from runner import JOB_NAME, benchmark_result, find_ccx, run_ccx

CCX = find_ccx()

pytestmark = pytest.mark.skipif(
    CCX is None,
    reason="ccx not found: set CCX or run inside the calculix-bench environment",
)

L = IPE200_TORSION.length
H_M = 191.5
B = 100.0
HALF_WEB = 2.8


@pytest.fixture(scope="module")
def coarse(tmp_path_factory):
    deck = generate_deck(IPE200_TORSION, COARSE)
    frd_path = run_ccx(deck.text, tmp_path_factory.mktemp("work") / COARSE.name, CCX)
    assert frd_path.name == f"{JOB_NAME}.frd"
    frd = read_frd(frd_path)
    return figure_series(benchmark_result(COARSE, IPE200_TORSION, deck, frd), frd, deck)


def test_twist_runs_root_to_tip_and_stays_between_vlasov_and_st_venant(coarse):
    x, phi = coarse.twist_x, coarse.twist_phi
    assert np.all(np.diff(x) > 0)
    assert (x[0], x[-1]) == pytest.approx((0.0, L))
    assert phi[0] == pytest.approx(0.0, abs=1e-9)
    assert np.all(np.diff(phi) > 0)
    assert phi[-1] == pytest.approx(0.27599, abs=1e-5)  # the report's coarse tip twist
    # Above Vlasov by up to the +5 % tip gap of the thin-walled J, far below St-Venant.
    inner = x > 0
    ratio = phi[inner] / twist_at(IPE200_TORSION, x[inner])
    assert np.all(ratio > 1.0)
    assert np.all(ratio < 1.06)
    assert phi[-1] < 0.8 * 0.35953


def test_quarter_span_stress_across_the_flanges_is_linear_and_changes_sign_at_the_web(coarse):
    # Thin-walled: sigma_w = -E y z phi''(L/4), +-58.68 MPa at z = -+b/2 on the top flange
    # (y = +h_m/2), the other way round on the bottom flange. The solid section sits about
    # +3.4 % above it at the flange tips (the report's coarse row) and follows the line across
    # the width.
    for z, sxx, y, outer_sign in (
        (coarse.top_flange_z, coarse.top_flange_sxx, H_M / 2, 1),
        (coarse.bottom_flange_z, coarse.bottom_flange_sxx, -H_M / 2, -1),
    ):
        assert np.all(np.diff(z) > 0)
        assert (z[0], z[-1]) == pytest.approx((-B / 2, B / 2))
        assert outer_sign * sxx[0] == pytest.approx(60.69, abs=0.01)
        assert outer_sign * sxx[-1] == pytest.approx(-60.69, abs=0.01)
        assert np.all(outer_sign * sxx[z < -HALF_WEB] > 0)
        assert np.all(outer_sign * sxx[z > HALF_WEB] < 0)
        expected = warping_stress_at(IPE200_TORSION, L / 4, y, z)
        assert sxx == pytest.approx(expected, abs=0.05 * 58.68)


def test_flange_tip_stress_decays_from_the_root_like_vlasov(coarse):
    x, sxx = coarse.flange_tip_x, coarse.flange_tip_sxx
    assert np.all(np.diff(x) > 0)
    assert (x[0], x[-1]) == pytest.approx((0.0, L))
    assert sxx[np.isclose(x, L / 4)] == pytest.approx(60.69, abs=0.01)  # the report's top -z
    # Between the root zone and the reach of the tip it follows Vlasov within the few % of the
    # thin-walled J. Towards the tip it levels off at about 14 MPa where Vlasov falls to a few
    # MPa, and drops back near zero only at the tip face, which is free to warp.
    assert np.all(np.diff(sxx[x > 0]) < 0)
    middle = (x >= 0.1 * L) & (x <= L / 3)
    expected = warping_stress_at(IPE200_TORSION, x[middle], H_M / 2, -B / 2)
    assert sxx[middle] == pytest.approx(expected, rel=0.06)
    assert sxx[np.isclose(x, 2500.0)] == pytest.approx(13.9, abs=0.1)
    assert abs(sxx[-1]) < 3.0


def test_convergence_point_carries_the_reported_coarse_values(coarse):
    # The coarse row of REPORT.md; the element length along x is L / 30.
    point = coarse.convergence
    assert point.element_length == pytest.approx(100.0)
    assert point.node_count == 3164
    assert point.tip_twist_error == pytest.approx(5.04, abs=0.01)
    assert point.warping_stress_error == pytest.approx(3.43, abs=0.01)
