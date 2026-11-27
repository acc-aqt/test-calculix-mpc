"""Hand-made result records for tests that don't need a solve."""

from analytical import analytical_solution
from benchmark_parameters import IPE200_TORSION
from runner import BenchmarkResult

VLASOV_TIP_TWIST = 0.26275
QUARTER_SPAN_WARPING_STRESS = 58.677
FLANGE_TIP_SIGNS = (1, -1, -1, 1)


def result(level, tip_ratio=1.0, stress_ratios=(1.0, 1.0, 1.0, 1.0), shear=69.1, root_peak=200.0):
    """A result record whose tip twist and flange-tip warping stresses are the given ratios of
    the Vlasov targets (top -z, top +z, bottom -z, bottom +z)."""
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
        midspan_st_venant_shear_stress=shear,
        root_peak_von_mises=root_peak,
        analytical=analytical_solution(IPE200_TORSION),
    )
