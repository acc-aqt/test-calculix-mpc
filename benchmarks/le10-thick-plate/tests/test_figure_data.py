import numpy as np
import pytest

from benchmark_parameters import COARSE, LE10
from deck import C3D20, C3D20R, generate_deck
from figure_data import figure_series
from frd import read_frd
from runner import benchmark_result, find_ccx, run_benchmark, run_ccx

CCX = find_ccx()

pytestmark = pytest.mark.skipif(
    CCX is None,
    reason="ccx not found: set CCX or run inside the calculix-bench environment",
)


@pytest.fixture(scope="module")
def coarse(tmp_path_factory):
    work_dir = tmp_path_factory.mktemp("work")
    deck = generate_deck(LE10, COARSE, C3D20R)
    frd_path = run_ccx(deck.text, work_dir / COARSE.name / C3D20R, CCX)
    frd = read_frd(frd_path)
    result = benchmark_result(COARSE, C3D20R, LE10, deck, frd, frd_path.with_suffix(".dat"))
    full_integration = run_benchmark(COARSE, LE10, work_dir, CCX, C3D20)
    return figure_series(result, LE10, deck, frd, full_integration)


def test_stress_through_the_thickness_at_d_runs_bottom_to_top_and_changes_sign(coarse):
    z, syy = coarse.thickness_z, coarse.thickness_syy
    assert np.all(np.diff(z) > 0)
    assert (z[0], z[-1]) == pytest.approx((-300.0, 300.0))
    assert len(z) == 2 * COARSE.thickness_divisions + 1
    # Bending about the hole: compression on the loaded top face, tension on the bottom.
    assert syy[-1] == pytest.approx(-5.424, abs=1e-3)  # the report's coarse σ_yy(D)
    assert syy[0] > 0
    assert np.count_nonzero(np.diff(np.sign(syy))) == 1


def test_hole_edge_series_runs_from_d_to_a_on_the_top_face(coarse):
    theta, syy = coarse.hole_edge_theta, coarse.hole_edge_syy
    assert np.all(np.diff(theta) > 0)
    assert (theta[0], theta[-1]) == pytest.approx((0.0, 90.0))
    assert len(theta) == 2 * COARSE.around_divisions + 1
    assert syy[0] == pytest.approx(-5.424, abs=1e-3)  # σ_yy(D)
    # At A the hole face's normal is y, so σ_yy is the traction-free normal stress there.
    assert abs(syy[-1]) < 0.1 * abs(syy[0])


def test_top_face_hole_edge_moves_down_under_the_pressure(coarse):
    uz = coarse.hole_edge_uz
    assert uz.shape == coarse.hole_edge_theta.shape
    assert np.all(uz < 0)


def test_convergence_point_carries_the_reported_coarse_values(coarse):
    # The coarse rows of REPORT.md, C3D20R and C3D20.
    point = coarse.convergence
    assert point.node_count == 349
    assert point.stress_yy_at_d == pytest.approx(-5.424, abs=1e-3)
    assert point.stress_yy_at_d_error == pytest.approx(0.82, abs=0.01)
    assert point.full_integration_stress_yy_at_d == pytest.approx(-5.523, abs=1e-3)
    assert point.full_integration_stress_yy_at_d_error == pytest.approx(2.66, abs=0.01)
