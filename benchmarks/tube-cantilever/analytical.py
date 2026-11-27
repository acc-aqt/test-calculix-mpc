"""Analytical solution for the tube cantilever: section properties and targets. No I/O."""

import math
from dataclasses import dataclass

import numpy as np

from benchmark_parameters import BenchmarkParameters

THIN_WALL_SHEAR_COEFFICIENT = 0.5


@dataclass(frozen=True)
class AnalyticalSolution:
    area: float
    second_moment_of_area: float
    shear_coefficient: float
    """Cowper's (1966) κ for a hollow circle."""
    outer_fibre_distance: float
    shear_modulus: float
    euler_bernoulli_deflection: float
    timoshenko_deflection: float
    """With the Cowper shear coefficient: the deflection target."""
    thin_wall_timoshenko_deflection: float
    """With the thin-wall κ = 0.5, for information."""
    midspan_stress: float
    """Magnitude of the bending stress at the outer fibre at x = L/2."""


def cowper_shear_coefficient(
    inner_radius: float, outer_radius: float, poissons_ratio: float
) -> float:
    nu = poissons_ratio
    m2 = (inner_radius / outer_radius) ** 2
    return 6 * (1 + nu) * (1 + m2) ** 2 / ((7 + 6 * nu) * (1 + m2) ** 2 + (20 + 12 * nu) * m2)


def analytical_solution(params: BenchmarkParameters) -> AnalyticalSolution:
    s = params.section
    r_o, r_i = s.outer_radius, s.inner_radius
    area = math.pi * (r_o**2 - r_i**2)
    second_moment = math.pi * (r_o**4 - r_i**4) / 4
    nu = params.material.poissons_ratio
    kappa = cowper_shear_coefficient(r_i, r_o, nu)

    load, length = params.tip_load, params.length
    e = params.material.youngs_modulus
    g = e / (2 * (1 + nu))
    euler_bernoulli = load * length**3 / (3 * e * second_moment)
    midspan_moment = load * length / 2

    return AnalyticalSolution(
        area=area,
        second_moment_of_area=second_moment,
        shear_coefficient=kappa,
        outer_fibre_distance=r_o,
        shear_modulus=g,
        euler_bernoulli_deflection=euler_bernoulli,
        timoshenko_deflection=euler_bernoulli + load * length / (kappa * g * area),
        thin_wall_timoshenko_deflection=(
            euler_bernoulli + load * length / (THIN_WALL_SHEAR_COEFFICIENT * g * area)
        ),
        midspan_stress=midspan_moment * r_o / second_moment,
    )


Position = float | np.ndarray


def euler_bernoulli_deflection_at(params: BenchmarkParameters, x: Position) -> Position:
    """Downward deflection magnitude at distance x from the root: P x² (3L − x) / (6 E I)."""
    s = analytical_solution(params)
    bending_stiffness = params.material.youngs_modulus * s.second_moment_of_area
    return params.tip_load * x**2 * (3 * params.length - x) / (6 * bending_stiffness)


def bending_stress_at(params: BenchmarkParameters, x: Position, y: Position) -> Position:
    """Beam-theory σ_xx = M(x)·y / I with M(x) = P (L − x): the −y tip load hogs the cantilever,
    so fibres above the neutral axis (+y) are in tension."""
    s = analytical_solution(params)
    return params.tip_load * (params.length - x) * y / s.second_moment_of_area


def timoshenko_deflection_at(params: BenchmarkParameters, x: Position) -> Position:
    """Euler-Bernoulli deflection at x plus the Cowper shear term P x / (κ G A)."""
    s = analytical_solution(params)
    shear_stiffness = s.shear_coefficient * s.shear_modulus * s.area
    return euler_bernoulli_deflection_at(params, x) + params.tip_load * x / shear_stiffness
