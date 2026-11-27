from dataclasses import replace

import numpy as np
import pytest

from analytical import (
    analytical_solution,
    bending_stress_at,
    euler_bernoulli_deflection_at,
    timoshenko_deflection_at,
)
from benchmark_parameters import IPE200_CANTILEVER


def test_ipe200_area_is_two_flanges_plus_web():
    # Flanges: 2 x 100 x 8.5 = 1700. Web: (200 - 2 x 8.5) x 5.6 = 183 x 5.6 = 1024.8.
    assert analytical_solution(IPE200_CANTILEVER).area == pytest.approx(2724.8)


def test_ipe200_second_moment_of_area_without_fillets():
    # Parallel-axis sum, flange centroid at (200 - 8.5) / 2 = 95.75 from the neutral axis:
    #   one flange: 100 x 8.5^3 / 12 + 850 x 95.75^2 = 5117.7 + 7792853.1 = 7797970.8
    #   web:        5.6 x 183^3 / 12                                     = 2859960.6
    #   I = 2 x 7797970.8 + 2859960.6                                    = 18455902.2
    # The tabulated IPE 200 value, 1.943e7, includes the root fillets this model omits.
    assert analytical_solution(IPE200_CANTILEVER).second_moment_of_area == pytest.approx(
        18455902.2, rel=1e-8
    )


def test_ipe200_shear_area_is_web_between_flange_mid_planes():
    # (200 - 8.5) x 5.6 = 191.5 x 5.6 = 1072.4
    assert analytical_solution(IPE200_CANTILEVER).shear_area == pytest.approx(1072.4)


def test_ipe200_outer_fibre_distance_is_half_the_height():
    assert analytical_solution(IPE200_CANTILEVER).outer_fibre_distance == pytest.approx(100.0)


def test_ipe200_euler_bernoulli_deflection():
    # P L^3 = 1e4 x 3000^3 = 2.7e14;  3 E I = 3 x 210000 x 18455902.2 = 1.16272184e13
    # 2.7e14 / 1.16272184e13 = 23.2214 mm
    # (22.06 mm with the tabulated, filleted I = 1.943e7.)
    assert analytical_solution(IPE200_CANTILEVER).euler_bernoulli_deflection == pytest.approx(
        23.2214, rel=1e-5
    )


def test_ipe200_timoshenko_deflection_adds_the_shear_term():
    # G = 210000 / (2 x 1.3) = 80769.23 MPa;  kappa G A_s = 80769.23 x 1072.4 = 8.66169e7 N
    # shear term = P L / (kappa G A_s) = 3e7 / 8.66169e7 = 0.34635 mm
    # Timoshenko = 23.2214 + 0.34635 = 23.5677 mm
    solution = analytical_solution(IPE200_CANTILEVER)
    shear_term = solution.timoshenko_deflection - solution.euler_bernoulli_deflection
    assert solution.shear_modulus == pytest.approx(80769.23, rel=1e-6)
    assert shear_term == pytest.approx(0.34635, rel=1e-4)
    assert solution.timoshenko_deflection == pytest.approx(23.5677, rel=1e-5)


def test_ipe200_midspan_stress_at_outer_fibres():
    # M(L/2) = 1e4 x 1500 = 1.5e7 N mm;  sigma = M c / I = 1.5e7 x 100 / 18455902.2 = 81.275 MPa
    assert analytical_solution(IPE200_CANTILEVER).midspan_stress == pytest.approx(81.275, rel=1e-5)


def test_overriding_the_length_changes_the_targets_but_not_the_section():
    # L = 4000: P L^3 / (3 E I) = 6.4e14 / 1.16272184e13 = 55.0433 mm
    #           sigma = 1e4 x 2000 x 100 / 18455902.2  = 108.366 MPa
    solution = analytical_solution(replace(IPE200_CANTILEVER, length=4000.0))
    assert solution.euler_bernoulli_deflection == pytest.approx(55.0433, rel=1e-5)
    assert solution.midspan_stress == pytest.approx(108.366, rel=1e-5)
    assert solution.second_moment_of_area == pytest.approx(18455902.2, rel=1e-8)


def test_deflection_curves_are_zero_at_the_root_and_the_tip_deflections_at_the_tip():
    solution = analytical_solution(IPE200_CANTILEVER)
    assert euler_bernoulli_deflection_at(IPE200_CANTILEVER, 0.0) == 0.0
    assert timoshenko_deflection_at(IPE200_CANTILEVER, 0.0) == 0.0
    assert euler_bernoulli_deflection_at(IPE200_CANTILEVER, 3000.0) == pytest.approx(
        solution.euler_bernoulli_deflection, rel=1e-12
    )
    assert timoshenko_deflection_at(IPE200_CANTILEVER, 3000.0) == pytest.approx(
        solution.timoshenko_deflection, rel=1e-12
    )


def test_deflection_curves_at_midspan():
    # x = 1500: P x^2 (3L - x) / (6 E I) = 1e4 x 2.25e6 x 7500 / 2.32544e13 = 7.25668 mm
    #           shear term P x / (kappa G A_s) = 1.5e7 / 8.66169e7          = 0.17318 mm
    assert euler_bernoulli_deflection_at(IPE200_CANTILEVER, 1500.0) == pytest.approx(
        7.25668, rel=1e-5
    )
    assert timoshenko_deflection_at(IPE200_CANTILEVER, 1500.0) == pytest.approx(7.42986, rel=1e-5)


def test_deflection_curves_accept_arrays_of_positions():
    x = np.array([0.0, 1500.0, 3000.0])
    assert timoshenko_deflection_at(IPE200_CANTILEVER, x) == pytest.approx(
        [0.0, 7.42986, 23.5677], rel=1e-5
    )


def test_bending_stress_is_tension_on_top_and_compression_below_under_the_tip_load():
    # M(x) = P (L - x). Midspan outer fibre: 1e4 x 1500 x 100 / 18455902.2 = 81.275 MPa;
    # root outer fibre twice that, 162.55 MPa.
    assert bending_stress_at(IPE200_CANTILEVER, 1500.0, 100.0) == pytest.approx(81.275, rel=1e-5)
    assert bending_stress_at(IPE200_CANTILEVER, 1500.0, -100.0) == pytest.approx(-81.275, rel=1e-5)
    assert bending_stress_at(IPE200_CANTILEVER, 0.0, 100.0) == pytest.approx(162.55, rel=1e-5)
    assert bending_stress_at(IPE200_CANTILEVER, 0.0, -100.0) == pytest.approx(-162.55, rel=1e-5)
    assert bending_stress_at(IPE200_CANTILEVER, 3000.0, 100.0) == 0.0
    assert bending_stress_at(IPE200_CANTILEVER, 1500.0, 0.0) == 0.0


def test_bending_stress_accepts_arrays_of_positions():
    x = np.array([0.0, 1500.0, 3000.0])
    assert bending_stress_at(IPE200_CANTILEVER, x, 100.0) == pytest.approx(
        [162.55, 81.275, 0.0], rel=1e-5
    )
