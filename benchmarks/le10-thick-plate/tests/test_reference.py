import pytest

from benchmark_parameters import LE10
from reference import quarter_annulus_volume, target_stress_at_d, top_face_area


def test_target_is_the_published_compressive_sigma_yy_at_d():
    assert target_stress_at_d() == -5.38


def test_top_face_area_is_the_quarter_annulus_between_the_ellipses():
    # pi/4 x (3250 x 2750 - 2000 x 1000) = pi/4 x 6 937 500 mm^2.
    assert top_face_area(LE10) == pytest.approx(5_448_699.8, rel=1e-7)


def test_volume_is_the_top_face_area_times_the_thickness():
    # 5 448 699.8 mm^2 x 600 mm = 3.2692 m^3.
    assert quarter_annulus_volume(LE10) == pytest.approx(3.2692199e9, rel=1e-7)
