from dataclasses import replace

import numpy as np
import pytest

from analytical import (
    analytical_solution,
    bending_stress_at,
    euler_bernoulli_deflection_at,
    timoshenko_deflection_at,
)
from benchmark_parameters import CHS168_CANTILEVER


def test_chs168_area_is_the_exact_annulus():
    # r_o = 84.15, r_i = 84.15 - 8 = 76.15
    # pi (r_o^2 - r_i^2) = pi (7081.2225 - 5798.8225) = pi x 1282.4 = 4028.78 mm^2
    assert analytical_solution(CHS168_CANTILEVER).area == pytest.approx(4028.78, rel=1e-6)


def test_chs168_second_moment_of_area_is_the_exact_annulus():
    # pi (r_o^4 - r_i^4) / 4 = pi (50143712.09 - 33626342.39) / 4 = pi x 16517369.71 / 4
    #                        = 1.29727e7 mm^4
    assert analytical_solution(CHS168_CANTILEVER).second_moment_of_area == pytest.approx(
        1.29727e7, rel=1e-5
    )


def test_chs168_cowper_shear_coefficient_for_a_hollow_circle():
    # m = 76.15 / 84.15 = 0.904932, m^2 = 0.818901, (1 + m^2)^2 = 3.308402
    # kappa = 6 x 1.3 x 3.308402 / (8.8 x 3.308402 + 23.6 x 0.818901)
    #       = 25.80554 / (29.11394 + 19.32607) = 25.80554 / 48.44001 = 0.53273
    assert analytical_solution(CHS168_CANTILEVER).shear_coefficient == pytest.approx(
        0.53273, rel=1e-5
    )


def test_chs168_euler_bernoulli_deflection():
    # P L^3 = 1e4 x 1000^3 = 1e13;  3 E I = 3 x 210000 x 1.29727e7 = 8.17281e12
    # 1e13 / 8.17281e12 = 1.22357 mm
    assert analytical_solution(CHS168_CANTILEVER).euler_bernoulli_deflection == pytest.approx(
        1.22357, rel=1e-5
    )


def test_chs168_timoshenko_deflection_adds_the_cowper_shear_term():
    # G = 210000 / 2.6 = 80769.23 MPa;  kappa G A = 0.53273 x 80769.23 x 4028.78 = 1.73352e8 N
    # shear term = P L / (kappa G A) = 1e7 / 1.73352e8 = 0.057686 mm
    # Timoshenko = 1.22357 + 0.057686 = 1.28126 mm
    solution = analytical_solution(CHS168_CANTILEVER)
    shear_term = solution.timoshenko_deflection - solution.euler_bernoulli_deflection
    assert solution.shear_modulus == pytest.approx(80769.23, rel=1e-6)
    assert shear_term == pytest.approx(0.057686, rel=1e-4)
    assert solution.timoshenko_deflection == pytest.approx(1.28126, rel=1e-5)


def test_chs168_thin_wall_deflection_uses_kappa_one_half():
    # 0.5 G A = 0.5 x 80769.23 x 4028.78 = 1.62701e8 N;  shear term = 1e7 / 1.62701e8 = 0.061463
    # 1.22357 + 0.061463 = 1.28503 mm
    assert analytical_solution(CHS168_CANTILEVER).thin_wall_timoshenko_deflection == (
        pytest.approx(1.28503, rel=1e-5)
    )


def test_chs168_midspan_stress_at_the_outer_fibre():
    # M(L/2) = 1e4 x 500 = 5e6 N mm;  sigma = M r_o / I = 5e6 x 84.15 / 1.29727e7 = 32.4335 MPa
    solution = analytical_solution(CHS168_CANTILEVER)
    assert solution.outer_fibre_distance == pytest.approx(84.15)
    assert solution.midspan_stress == pytest.approx(32.4335, rel=1e-5)


def test_overriding_the_length_changes_the_targets_but_not_the_section():
    # L = 2000: P L^3 / (3 E I) = 8e13 / 8.17281e12 = 9.78855 mm
    #           sigma = 1e4 x 1000 x 84.15 / 1.29727e7 = 64.8669 MPa
    solution = analytical_solution(replace(CHS168_CANTILEVER, length=2000.0))
    assert solution.euler_bernoulli_deflection == pytest.approx(9.78855, rel=1e-5)
    assert solution.midspan_stress == pytest.approx(64.8669, rel=1e-5)
    assert solution.second_moment_of_area == pytest.approx(1.29727e7, rel=1e-5)


def test_deflection_curves_are_zero_at_the_root_and_the_tip_deflections_at_the_tip():
    solution = analytical_solution(CHS168_CANTILEVER)
    assert euler_bernoulli_deflection_at(CHS168_CANTILEVER, 0.0) == 0.0
    assert timoshenko_deflection_at(CHS168_CANTILEVER, 0.0) == 0.0
    assert euler_bernoulli_deflection_at(CHS168_CANTILEVER, 1000.0) == pytest.approx(
        solution.euler_bernoulli_deflection, rel=1e-12
    )
    assert timoshenko_deflection_at(CHS168_CANTILEVER, 1000.0) == pytest.approx(
        solution.timoshenko_deflection, rel=1e-12
    )


def test_deflection_curves_at_midspan():
    # x = 500: P x^2 (3L - x) / (6 E I) = 1e4 x 2.5e5 x 2500 / 1.634562e13 = 0.382366 mm
    #          shear term P x / (kappa G A) = 5e6 / 1.73352e8                = 0.028843 mm
    assert euler_bernoulli_deflection_at(CHS168_CANTILEVER, 500.0) == pytest.approx(
        0.382366, rel=1e-5
    )
    assert timoshenko_deflection_at(CHS168_CANTILEVER, 500.0) == pytest.approx(0.411209, rel=1e-5)


def test_deflection_curves_accept_arrays_of_positions():
    x = np.array([0.0, 500.0, 1000.0])
    assert timoshenko_deflection_at(CHS168_CANTILEVER, x) == pytest.approx(
        [0.0, 0.411209, 1.28126], rel=1e-5
    )


def test_bending_stress_is_tension_on_top_and_compression_below_under_the_tip_load():
    # M(x) = P (L - x). Midspan outer fibre: 1e4 x 500 x 84.15 / 1.29727e7 = 32.4335 MPa;
    # root outer fibre twice that, 64.8669 MPa.
    assert bending_stress_at(CHS168_CANTILEVER, 500.0, 84.15) == pytest.approx(32.4335, rel=1e-5)
    assert bending_stress_at(CHS168_CANTILEVER, 500.0, -84.15) == pytest.approx(-32.4335, rel=1e-5)
    assert bending_stress_at(CHS168_CANTILEVER, 0.0, 84.15) == pytest.approx(64.8669, rel=1e-5)
    assert bending_stress_at(CHS168_CANTILEVER, 1000.0, 84.15) == 0.0
    assert bending_stress_at(CHS168_CANTILEVER, 500.0, 0.0) == 0.0


def test_bending_stress_accepts_arrays_of_positions():
    x = np.array([0.0, 500.0, 1000.0])
    assert bending_stress_at(CHS168_CANTILEVER, x, 84.15) == pytest.approx(
        [64.8669, 32.4335, 0.0], rel=1e-5
    )
