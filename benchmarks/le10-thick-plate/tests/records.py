"""Hand-made result records for tests that don't need a solve."""

from benchmark_parameters import COARSE, FINE, MEDIUM
from runner import BenchmarkResult

PUBLISHED_STRESS_AT_D = -5.38


def result(level, stress_ratio=1.0, sxx=-0.3566, integration_point_stress_yy=-3.8198):
    """A result record whose σ_yy(D) is the given ratio of the published −5.38 MPa, with the
    other components and the integration point shaped like the coarse prototype run."""
    return BenchmarkResult(
        mesh_level=level,
        element_count=48,
        node_count=349,
        stress_at_d=(
            sxx,
            PUBLISHED_STRESS_AT_D * stress_ratio,
            -1.0853,
            0.0603,
            -0.0194,
            -0.0543,
        ),
        integration_point_at_d=(2062.845, 60.565, 236.6025),
        integration_point_stress_yy_at_d=integration_point_stress_yy,
    )


def levels(coarse_ratio, medium_ratio, fine_ratio):
    """Coarse, medium and fine result records with the given σ_yy(D) ratios."""
    return [
        result(COARSE, coarse_ratio),
        result(MEDIUM, medium_ratio),
        result(FINE, fine_ratio),
    ]
