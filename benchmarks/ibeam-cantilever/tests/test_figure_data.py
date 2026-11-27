import numpy as np
import pytest

from analytical import timoshenko_deflection_at
from benchmark_parameters import COARSE, IPE200_CANTILEVER
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
    result = run_benchmark(COARSE, IPE200_CANTILEVER, work_dir, CCX)
    frd = read_frd(work_dir / COARSE.name / f"{JOB_NAME}.frd")
    return figure_series(result, frd, IPE200_CANTILEVER)


def test_web_centreline_deflection_runs_root_to_tip_and_matches_timoshenko(coarse):
    x, v = coarse.deflection_x, coarse.deflection_v
    assert np.all(np.diff(x) > 0)
    assert (x[0], x[-1]) == pytest.approx((0.0, 3000.0))
    assert v[0] == pytest.approx(0.0, abs=1e-9)
    # Within 1 % of the tip deflection everywhere. Not 1 % pointwise: the fixed root face holds
    # back shear deformation, so near the root the FE curve sits about 0.01 mm below Timoshenko.
    tip = timoshenko_deflection_at(IPE200_CANTILEVER, 3000.0)
    assert v == pytest.approx(timoshenko_deflection_at(IPE200_CANTILEVER, x), abs=0.01 * tip)


def test_midspan_stress_through_the_depth_is_linear_m_y_over_i(coarse):
    # M(L/2) / I = 10000 x 1500 / 18455902.2 = 0.81275 MPa/mm: +81.27 at y = 100, -81.27 at -100.
    y, sxx = coarse.depth_y, coarse.depth_sxx
    assert np.all(np.diff(y) > 0)
    assert (y[0], y[-1]) == pytest.approx((-100.0, 100.0))
    assert sxx == pytest.approx(0.81275 * y, abs=0.01 * 81.27)


def test_top_flange_stress_follows_the_moment_diagram_away_from_the_ends(coarse):
    # P (L - x) c / I = 10000 x (3000 - x) x 100 / 18455902.2 = 0.054183 x (3000 - x) MPa.
    x, sxx = coarse.top_flange_x, coarse.top_flange_sxx
    assert np.all(np.diff(x) > 0)
    assert (x[0], x[-1]) == pytest.approx((0.0, 3000.0))
    middle = (x >= 600) & (x <= 2400)
    assert sxx[middle] == pytest.approx(0.054183 * (3000 - x[middle]), rel=0.01)
    assert sxx[x == 1500.0] == pytest.approx(81.2709, abs=1e-4)  # the report's width mean


def test_convergence_point_carries_the_reported_coarse_values(coarse):
    # The coarse row of REPORT.md.
    point = coarse.convergence
    assert point.node_count == 3164
    assert point.reference_node_deflection == pytest.approx(23.5576, abs=1e-4)
    assert point.deflection_error == pytest.approx(-0.043, abs=1e-3)
    assert point.top_stress_error == pytest.approx(-0.005, abs=1e-3)
    assert point.bottom_stress_error == pytest.approx(-0.005, abs=1e-3)
    assert point.root_peak_von_mises == pytest.approx(169.67, abs=0.01)
