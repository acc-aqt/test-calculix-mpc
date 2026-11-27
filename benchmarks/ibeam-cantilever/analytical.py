"""Analytical solution for the cantilever: section properties and targets. No I/O."""

from dataclasses import dataclass

from benchmark_parameters import BenchmarkParameters

SHEAR_COEFFICIENT = 1.0


@dataclass(frozen=True)
class AnalyticalSolution:
    area: float
    second_moment_of_area: float
    shear_area: float
    outer_fibre_distance: float
    shear_modulus: float
    euler_bernoulli_deflection: float
    timoshenko_deflection: float
    midspan_stress: float
    """Magnitude of the bending stress at the outer fibres at x = L/2."""


def analytical_solution(params: BenchmarkParameters) -> AnalyticalSolution:
    s = params.section
    web_height = s.height - 2 * s.flange_thickness
    area = 2 * s.flange_width * s.flange_thickness + web_height * s.web_thickness
    outer_box = s.flange_width * s.height**3 / 12
    cutouts = (s.flange_width - s.web_thickness) * web_height**3 / 12
    second_moment = outer_box - cutouts
    shear_area = (s.height - s.flange_thickness) * s.web_thickness

    load, length = params.tip_load, params.length
    e = params.material.youngs_modulus
    g = e / (2 * (1 + params.material.poissons_ratio))
    euler_bernoulli = load * length**3 / (3 * e * second_moment)
    shear_term = load * length / (SHEAR_COEFFICIENT * g * shear_area)
    outer_fibre_distance = s.height / 2
    midspan_moment = load * length / 2

    return AnalyticalSolution(
        area=area,
        second_moment_of_area=second_moment,
        shear_area=shear_area,
        outer_fibre_distance=outer_fibre_distance,
        shear_modulus=g,
        euler_bernoulli_deflection=euler_bernoulli,
        timoshenko_deflection=euler_bernoulli + shear_term,
        midspan_stress=midspan_moment * outer_fibre_distance / second_moment,
    )
