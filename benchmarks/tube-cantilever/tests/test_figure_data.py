import numpy as np
import pytest

from analytical import timoshenko_deflection_at
from benchmark_parameters import CHS168_CANTILEVER, COARSE
from figure_data import figure_series
from frd import read_frd
from runner import JOB_NAME, find_ccx, run_benchmark

CCX = find_ccx()

pytestmark = pytest.mark.skipif(
    CCX is None,
    reason="ccx not found: set CCX or run inside the calculix-bench environment",
)


@pytest.fixture(scope="module")
def coarse(tmp_path_factory):
    work_dir = tmp_path_factory.mktemp("work")
    result = run_benchmark(COARSE, CHS168_CANTILEVER, work_dir, CCX)
    frd = read_frd(work_dir / COARSE.name / f"{JOB_NAME}.frd")
    return figure_series(result, frd, CHS168_CANTILEVER)


def test_section_mean_deflection_runs_root_to_tip_and_matches_timoshenko(coarse):
    x, v = coarse.deflection_x, coarse.deflection_v
    assert np.all(np.diff(x) > 0)
    assert (x[0], x[-1]) == pytest.approx((0.0, 1000.0))
    assert v[0] == pytest.approx(0.0, abs=1e-9)
    tip = timoshenko_deflection_at(CHS168_CANTILEVER, 1000.0)
    assert v == pytest.approx(timoshenko_deflection_at(CHS168_CANTILEVER, x), abs=0.01 * tip)
    assert v[-1] == pytest.approx(1.28222, abs=1e-5)  # the report's coarse tip-face mean


def test_midspan_stress_around_the_outer_surface_is_linear_m_y_over_i(coarse):
    # M(L/2) / I = 10000 x 500 / 12972711.8 = 0.385424 MPa/mm: ±32.43 MPa at y = ±84.15.
    y, sxx = coarse.circumference_y, coarse.circumference_sxx
    assert len(y) == 16  # 8 corner and 8 midside nodes around the coarse circumference
    assert np.all(np.diff(y) >= 0)
    assert (y[0], y[-1]) == pytest.approx((-84.15, 84.15))
    # The coarse single-node error at the fibres is +5 %; the fit through all nodes is +1.354 %.
    assert sxx == pytest.approx(0.385424 * y, abs=0.06 * 32.4335)
    slope = np.sum(y * sxx) / np.sum(y * y)
    assert slope * 84.15 == pytest.approx(32.8727, abs=1e-4)  # the report's coarse fit


def test_top_fibre_stress_follows_the_moment_diagram_away_from_the_ends(coarse):
    # P (L - x) r_o / I = 10000 x (1000 - x) x 84.15 / 12972711.8 = 0.064867 x (1000 - x) MPa.
    x, sxx = coarse.top_fibre_x, coarse.top_fibre_sxx
    assert np.all(np.diff(x) > 0)
    assert (x[0], x[-1]) == pytest.approx((0.0, 1000.0))
    middle = (x >= 168.3) & (x <= 1000 - 168.3)  # more than one diameter from either end
    # About +5 % like the midspan top node, swinging a few % between corner and midside nodes
    # along the coarse level's 100 mm elements.
    assert sxx[middle] == pytest.approx(0.064867 * (1000 - x[middle]), rel=0.09)
    assert sxx[x == 500.0] == pytest.approx(34.0544, abs=1e-4)  # the report's top node


def test_convergence_point_carries_the_reported_coarse_values(coarse):
    # The coarse row of REPORT.md; the element size is the outer arc 2π x 84.15 / 8.
    point = coarse.convergence
    assert point.element_size == pytest.approx(66.0913, abs=1e-4)
    assert point.node_count == 601
    assert point.deflection_error == pytest.approx(0.076, abs=1e-3)
    assert point.fitted_stress_errors == pytest.approx((1.354, 1.354), abs=1e-3)
    assert point.single_node_stress_errors == pytest.approx((4.998, 4.998), abs=1e-3)
    assert point.root_peak_von_mises == pytest.approx(66.44, abs=0.01)
