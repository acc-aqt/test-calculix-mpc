"""The published LE10 target and the exact geometry the guards compare the mesh with.

See ADR 0004 for where −5.38 MPa comes from.
"""

import math

from benchmark_parameters import BenchmarkParameters

PUBLISHED_STRESS_AT_D = -5.38
"""σ_yy at point D in MPa, compressive. Some sources quote the magnitude 5.38."""


def target_stress_at_d() -> float:
    return PUBLISHED_STRESS_AT_D


def stress_at_d_error(stress_yy: float) -> float:
    """The error of a σ_yy(D) in %, (FE − target) / target × 100, signed against the signed
    target, so a flipped sign gives about −200 %."""
    target = target_stress_at_d()
    return (stress_yy - target) / target * 100


def top_face_area(params: BenchmarkParameters) -> float:
    """The quarter annulus between the inner and outer ellipses, (π/4)(a_o·b_o − a_i·b_i)."""
    outer, inner = params.outer, params.inner
    ellipse_products = outer.semi_axis_x * outer.semi_axis_y - inner.semi_axis_x * inner.semi_axis_y
    return math.pi / 4 * ellipse_products


def quarter_annulus_volume(params: BenchmarkParameters) -> float:
    return top_face_area(params) * params.thickness
