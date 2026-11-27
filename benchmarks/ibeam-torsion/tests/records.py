"""Hand-made result records for tests that don't need a solve."""

import numpy as np

from analytical import analytical_solution, warping_stress_at
from benchmark_parameters import IPE200_TORSION
from runner import BenchmarkResult

VLASOV_TIP_TWIST = 0.26275
QUARTER_SPAN_WARPING_STRESS = 58.677
FLANGE_TIP_SIGNS = (1, -1, -1, 1)


def flange_tip_stress_curve(onset=1200.0, plateau=(17.0, 12.0), quarter_ratio=0.9953):
    """(x, σ_xx) every 50 mm along the top flange tip at z = -b/2, shaped like the committed
    fine run: the end-corrected Vlasov curve, quarter_ratio of it at L/4, 5 % above it from
    onset on, falling linearly from plateau[0] to plateau[1] over x = 2000 to 2800 mm, and zero
    at the tip face."""
    solution = analytical_solution(IPE200_TORSION)
    y, z = solution.flange_mid_plane_distance / 2, -IPE200_TORSION.section.flange_width / 2
    length = IPE200_TORSION.length
    x = np.linspace(0.0, length, 61)
    sxx = warping_stress_at(
        IPE200_TORSION, x, y, z, torsion_constant=solution.end_corrected_torsion_constant
    )
    sxx[np.isclose(x, length / 4)] *= quarter_ratio
    sxx[x >= onset] *= 1.05
    in_plateau = (x >= 2000.0) & (x <= 2800.0)
    sxx[in_plateau] = np.linspace(*plateau, in_plateau.sum())
    sxx[-1] = 0.0
    return tuple(zip(x.tolist(), sxx.tolist(), strict=True))


def result(
    level,
    tip_ratio=1.0,
    stress_ratios=(1.0, 1.0, 1.0, 1.0),
    shear=69.1,
    root_peak=200.0,
    flange_tip_curve=None,
):
    """A result record whose tip twist and flange-tip warping stresses are the given ratios of
    the Vlasov targets (top -z, top +z, bottom -z, bottom +z), with flange_tip_stress_curve()
    unless another flange-tip curve is given."""
    tip = VLASOV_TIP_TWIST * tip_ratio
    return BenchmarkResult(
        mesh_level=level,
        element_count=420,
        node_count=3164,
        twist_curve=((0.0, 0.0), (1500.0, tip / 3), (3000.0, tip)),
        flange_tip_warping_stresses=tuple(
            sign * ratio * QUARTER_SPAN_WARPING_STRESS
            for sign, ratio in zip(FLANGE_TIP_SIGNS, stress_ratios, strict=True)
        ),
        flange_tip_stress_curve=flange_tip_curve or flange_tip_stress_curve(),
        midspan_st_venant_shear_stress=shear,
        root_peak_von_mises=root_peak,
        analytical=analytical_solution(IPE200_TORSION),
    )
