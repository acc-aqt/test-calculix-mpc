"""Vlasov mixed torsion of the cantilever: section properties, targets and curves. No I/O.

The root (x = 0) is fixed and so restrains warping; the tip (x = L) is free to warp. With
T about +x and the torsion parameter λ = √(GJ / (E·I_w)):

    φ(x)   = T/(GJ)·[x − (sinh λL − sinh λ(L − x)) / (λ·cosh λL)]
    φ'(x)  = T/(GJ)·[1 − cosh λ(L − x) / cosh λL]
    φ''(x) = T/(GJ)·λ·sinh λ(L − x) / cosh λL
"""

from dataclasses import dataclass

import numpy as np

from benchmark_parameters import BenchmarkParameters

Position = float | np.ndarray


@dataclass(frozen=True)
class AnalyticalSolution:
    shear_modulus: float
    torsion_constant: float
    """J = (2·b·t_f³ + (h − 2t_f)·t_w³) / 3."""
    flange_second_moment: float
    """I_f = t_f·b³ / 12, one flange about its own vertical axis."""
    flange_mid_plane_distance: float
    """h_m = h − t_f."""
    warping_constant: float
    """I_w = I_f·h_m² / 2."""
    torsion_parameter: float
    torsion_parameter_times_length: float
    flange_tip_sectorial_coordinate: float
    """ω = h_m·b / 4, magnitude at the four flange tips."""
    st_venant_tip_twist: float
    """φ_SV(L) = T·L / (GJ), information only."""
    tip_twist: float
    """Vlasov φ(L), the twist target."""
    quarter_span_warping_stress: float
    """Magnitude E·ω·φ''(L/4) at the flange tips, the warping stress target."""
    root_warping_stress: float
    """Magnitude E·ω·φ''(0), information only."""
    midspan_st_venant_shear_stress: float
    """G·t_f·φ'(L/2) at the flange outer surface, information only."""
    end_corrected_torsion_constant: float
    """J with the end correction (1 − 0.63·t/b) on each plate, information only."""
    end_corrected_tip_twist: float
    """Vlasov φ(L) with the end-corrected J, information only."""
    end_corrected_quarter_span_warping_stress: float
    """E·ω·φ''(L/4) with the end-corrected J, information only."""


def analytical_solution(params: BenchmarkParameters) -> AnalyticalSolution:
    s = params.section
    e = params.material.youngs_modulus
    g, j, flange_second_moment, h_m, warping_constant, lam = _section_properties(params)
    omega = h_m * s.flange_width / 4
    length = params.length
    end_corrected_j = _end_corrected_torsion_constant(params)
    return AnalyticalSolution(
        shear_modulus=g,
        torsion_constant=j,
        flange_second_moment=flange_second_moment,
        flange_mid_plane_distance=h_m,
        warping_constant=warping_constant,
        torsion_parameter=lam,
        torsion_parameter_times_length=lam * length,
        flange_tip_sectorial_coordinate=omega,
        st_venant_tip_twist=float(st_venant_twist_at(params, length)),
        tip_twist=float(twist_at(params, length)),
        quarter_span_warping_stress=float(e * omega * twist_curvature_at(params, length / 4)),
        root_warping_stress=float(e * omega * twist_curvature_at(params, 0.0)),
        midspan_st_venant_shear_stress=float(
            g * s.flange_thickness * twist_rate_at(params, length / 2)
        ),
        end_corrected_torsion_constant=end_corrected_j,
        end_corrected_tip_twist=_vlasov_tip_twist(params, g, end_corrected_j, warping_constant),
        end_corrected_quarter_span_warping_stress=_vlasov_quarter_span_warping_stress(
            params, g, end_corrected_j, warping_constant, omega
        ),
    )


def twist_at(params: BenchmarkParameters, x: Position) -> Position:
    """Vlasov twist φ(x) in rad."""
    scale, lam, length = _curve_constants(params)
    warping = (np.sinh(lam * length) - np.sinh(lam * (length - x))) / (lam * np.cosh(lam * length))
    return scale * (x - warping)


def twist_rate_at(params: BenchmarkParameters, x: Position) -> Position:
    """φ'(x) in rad/mm."""
    scale, lam, length = _curve_constants(params)
    return scale * (1 - np.cosh(lam * (length - x)) / np.cosh(lam * length))


def twist_curvature_at(params: BenchmarkParameters, x: Position) -> Position:
    """φ''(x) in rad/mm²."""
    scale, lam, length = _curve_constants(params)
    return scale * lam * np.sinh(lam * (length - x)) / np.cosh(lam * length)


def st_venant_twist_at(params: BenchmarkParameters, x: Position) -> Position:
    """Pure St-Venant twist T·x / (GJ), the line the Vlasov curve stays below."""
    scale, _, _ = _curve_constants(params)
    return scale * x


def warping_stress_at(
    params: BenchmarkParameters, x: Position, y: Position, z: Position
) -> Position:
    """σ_w = −E·ω·φ''(x) at a flange mid-plane point, with sectorial coordinate ω = y·z.

    The sign follows from T about +x: the top flange bends laterally towards +z, which
    compresses its +z edge.
    """
    e = params.material.youngs_modulus
    return -e * y * z * twist_curvature_at(params, x)


def _end_corrected_torsion_constant(params: BenchmarkParameters) -> float:
    """(2·b·t_f³·(1 − 0.63·t_f/b) + h_w·t_w³·(1 − 0.63·t_w/h_w)) / 3, h_w = h − 2t_f."""
    s = params.section
    web_height = s.height - 2 * s.flange_thickness
    flanges = (
        2
        * s.flange_width
        * s.flange_thickness**3
        * (1 - 0.63 * s.flange_thickness / s.flange_width)
    )
    web = web_height * s.web_thickness**3 * (1 - 0.63 * s.web_thickness / web_height)
    return (flanges + web) / 3


def _vlasov_tip_twist(
    params: BenchmarkParameters, g: float, j: float, warping_constant: float
) -> float:
    """φ(L) = T/(GJ)·(L − tanh(λL)/λ) for a given J."""
    lam = np.sqrt(g * j / (params.material.youngs_modulus * warping_constant))
    length = params.length
    return float(params.torque / (g * j) * (length - np.tanh(lam * length) / lam))


def _vlasov_quarter_span_warping_stress(
    params: BenchmarkParameters, g: float, j: float, warping_constant: float, omega: float
) -> float:
    """E·ω·φ''(L/4) for a given J."""
    e = params.material.youngs_modulus
    lam = np.sqrt(g * j / (e * warping_constant))
    length = params.length
    curvature = params.torque / (g * j) * lam * np.sinh(0.75 * lam * length) / np.cosh(lam * length)
    return float(e * omega * curvature)


def _curve_constants(params: BenchmarkParameters) -> tuple[float, float, float]:
    """T/(GJ), λ and L."""
    g, j, _, _, _, lam = _section_properties(params)
    return params.torque / (g * j), lam, params.length


def _section_properties(
    params: BenchmarkParameters,
) -> tuple[float, float, float, float, float, float]:
    """G, J, I_f, h_m, I_w and λ."""
    s = params.section
    e = params.material.youngs_modulus
    g = e / (2 * (1 + params.material.poissons_ratio))
    web_height = s.height - 2 * s.flange_thickness
    j = (2 * s.flange_width * s.flange_thickness**3 + web_height * s.web_thickness**3) / 3
    flange_second_moment = s.flange_thickness * s.flange_width**3 / 12
    h_m = s.height - s.flange_thickness
    warping_constant = flange_second_moment * h_m**2 / 2
    lam = float(np.sqrt(g * j / (e * warping_constant)))
    return g, j, flange_second_moment, h_m, warping_constant, lam
