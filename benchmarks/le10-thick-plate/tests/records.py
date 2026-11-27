"""Hand-made result records for tests that don't need a solve."""

from deck import C3D20R
from runner import BenchmarkResult

PUBLISHED_STRESS_AT_D = -5.38


def result(level, stress_ratio=1.0, element_type=C3D20R):
    """A result record whose σ_yy(D) is the given ratio of the published −5.38 MPa, with the
    other components and the integration point shaped like the coarse prototype run."""
    return BenchmarkResult(
        mesh_level=level,
        element_type=element_type,
        element_count=48,
        node_count=349,
        stress_at_d=(
            -0.3566,
            PUBLISHED_STRESS_AT_D * stress_ratio,
            -1.0853,
            0.0603,
            -0.0194,
            -0.0543,
        ),
        integration_point_at_d=(2062.845, 60.565, 236.6025),
        integration_point_stress_yy_at_d=-3.8198,
        reaction_z_on_ee=5.448647e6,
        mesh_volume=3.269188e9,
    )
