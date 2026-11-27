import numpy as np
import pytest

from analytical import (
    analytical_solution,
    st_venant_twist_at,
    twist_at,
    twist_curvature_at,
    twist_rate_at,
    warping_stress_at,
)
from benchmark_parameters import IPE200_TORSION

# Hand-checked values from the spec (#23) for the no-fillet IPE 200, L = 3000 mm, T = 5e5 N mm.
L = IPE200_TORSION.length
SOLUTION = analytical_solution(IPE200_TORSION)


def test_shear_modulus_from_e_and_nu():
    # 210000 / (2 x 1.3) = 80769.2 MPa
    assert SOLUTION.shear_modulus == pytest.approx(80_769.2, rel=1e-6)


def test_st_venant_torsion_constant_is_the_thin_walled_sum_of_b_t_cubed_over_three():
    # (2 x 100 x 8.5^3 + 183 x 5.6^3) / 3 = (122825 + 32137.7) / 3 = 51654.2 mm^4
    assert SOLUTION.torsion_constant == pytest.approx(51_654.2, rel=1e-6)


def test_warping_constant_from_the_flange_second_moment_and_mid_plane_distance():
    # I_f = 8.5 x 100^3 / 12 = 708333.3 mm^4, h_m = 191.5 mm, I_w = I_f h_m^2 / 2
    assert SOLUTION.flange_second_moment == pytest.approx(708_333.3, rel=1e-6)
    assert SOLUTION.flange_mid_plane_distance == pytest.approx(191.5)
    assert SOLUTION.warping_constant == pytest.approx(1.2988e10, rel=1e-4)


def test_torsion_parameter_and_lambda_l():
    assert SOLUTION.torsion_parameter == pytest.approx(1.23678e-3, rel=1e-5)
    assert SOLUTION.torsion_parameter_times_length == pytest.approx(3.7104, rel=1e-4)


def test_st_venant_tip_twist_for_information():
    assert SOLUTION.st_venant_tip_twist == pytest.approx(0.35953, rel=1e-4)


def test_vlasov_tip_twist_target_is_about_73_percent_of_st_venant():
    assert SOLUTION.tip_twist == pytest.approx(0.26275, rel=1e-4)
    assert SOLUTION.tip_twist / SOLUTION.st_venant_tip_twist == pytest.approx(0.731, abs=5e-4)


def test_flange_tip_sectorial_coordinate():
    # h_m b / 4 = 191.5 x 100 / 4
    assert SOLUTION.flange_tip_sectorial_coordinate == pytest.approx(4787.5)


def test_warping_stresses_at_quarter_span_and_root():
    assert SOLUTION.quarter_span_warping_stress == pytest.approx(58.68, rel=1e-3)
    assert SOLUTION.root_warping_stress == pytest.approx(148.84, rel=1e-4)


def test_st_venant_shear_stress_at_midspan_flange_surface():
    assert SOLUTION.midspan_st_venant_shear_stress == pytest.approx(69.10, rel=1e-3)


def test_twist_curve_starts_at_zero_with_zero_slope_and_reaches_the_tip_target():
    assert twist_at(IPE200_TORSION, 0.0) == pytest.approx(0.0, abs=1e-15)
    assert twist_rate_at(IPE200_TORSION, 0.0) == pytest.approx(0.0, abs=1e-15)
    assert twist_at(IPE200_TORSION, L) == pytest.approx(SOLUTION.tip_twist)


def test_twist_curvature_vanishes_at_the_warping_free_tip():
    assert twist_curvature_at(IPE200_TORSION, L) == pytest.approx(0.0, abs=1e-15)


def test_twist_curve_is_below_the_st_venant_line_and_takes_arrays():
    xs = np.linspace(L / 10, L, 10)
    assert np.all(twist_at(IPE200_TORSION, xs) < st_venant_twist_at(IPE200_TORSION, xs))
    assert st_venant_twist_at(IPE200_TORSION, L) == pytest.approx(SOLUTION.st_venant_tip_twist)


def test_warping_stress_at_a_flange_tip_has_the_target_magnitude_at_quarter_span():
    h_m, b = SOLUTION.flange_mid_plane_distance, IPE200_TORSION.section.flange_width
    value = warping_stress_at(IPE200_TORSION, L / 4, h_m / 2, b / 2)
    assert abs(value) == pytest.approx(58.68, rel=1e-3)
    assert warping_stress_at(IPE200_TORSION, L / 2, h_m / 2, b / 2) == pytest.approx(
        -22.73, rel=1e-3
    )


def test_warping_stress_changes_sign_across_the_web_and_between_the_flanges():
    # A torque about +x moves the top flange towards +z; its lateral curvature puts the +z edge
    # of the top flange in compression and the -z edge in tension, and the bottom flange the
    # other way round.
    h_m, b = SOLUTION.flange_mid_plane_distance, IPE200_TORSION.section.flange_width
    x = L / 4
    assert warping_stress_at(IPE200_TORSION, x, h_m / 2, b / 2) < 0
    assert warping_stress_at(IPE200_TORSION, x, h_m / 2, -b / 2) > 0
    assert warping_stress_at(IPE200_TORSION, x, -h_m / 2, b / 2) > 0
    assert warping_stress_at(IPE200_TORSION, x, -h_m / 2, -b / 2) < 0
    assert warping_stress_at(IPE200_TORSION, x, h_m / 2, 0.0) == 0.0


def test_end_corrected_torsion_constant_for_information():
    # Flanges: 2 x 100 x 8.5^3 x (1 - 0.63 x 8.5/100) = 122825 x 0.946450 = 116247.7
    # Web: 183 x 5.6^3 x (1 - 0.63 x 5.6/183) = 32137.7 x 0.980721 = 31518.2
    # (116247.7 + 31518.2) / 3 = 49255.3 mm^4, 4.6 % below the thin-walled J
    assert SOLUTION.end_corrected_torsion_constant == pytest.approx(49_255.3, rel=1e-6)


def test_vlasov_tip_twist_with_the_end_corrected_torsion_constant_for_information():
    # lambda L = 3.6232 with J = 49255.3; T/(GJ) x (L - tanh(lambda L)/lambda) = 0.27313 rad
    assert SOLUTION.end_corrected_tip_twist == pytest.approx(0.27313, rel=1e-4)
