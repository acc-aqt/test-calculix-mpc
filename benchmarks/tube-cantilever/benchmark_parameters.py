"""The benchmark case in one place. Units: N, mm, MPa.

Override a value with dataclasses.replace, e.g.
    replace(CHS168_CANTILEVER, length=2000.0)
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TubeSection:
    """Circular hollow section."""

    outer_radius: float
    wall_thickness: float

    @property
    def inner_radius(self) -> float:
        return self.outer_radius - self.wall_thickness


@dataclass(frozen=True)
class Material:
    youngs_modulus: float
    poissons_ratio: float


@dataclass(frozen=True)
class BenchmarkParameters:
    section: TubeSection
    length: float
    material: Material
    tip_load: float
    """Magnitude of the tip load; it acts in -y."""


CHS168_CANTILEVER = BenchmarkParameters(
    section=TubeSection(outer_radius=84.15, wall_thickness=8.0),
    length=1000.0,
    material=Material(youngs_modulus=210_000.0, poissons_ratio=0.3),
    tip_load=10_000.0,
)


@dataclass(frozen=True)
class MeshLevel:
    """Element counts around the circumference, through the wall and along the length.

    The circumferential divisions must be a multiple of 4 and the length divisions even, so that
    0°, 90°, 180°, 270° and x = L/2 fall on nodes.
    """

    name: str
    circumferential_divisions: int
    wall_divisions: int
    length_divisions: int

    @property
    def label(self) -> str:
        """Name and divisions, e.g. "coarse 8/1/10"."""
        return (
            f"{self.name} {self.circumferential_divisions}/{self.wall_divisions}/"
            f"{self.length_divisions}"
        )


COARSE = MeshLevel("coarse", circumferential_divisions=8, wall_divisions=1, length_divisions=10)
MEDIUM = MeshLevel("medium", circumferential_divisions=16, wall_divisions=2, length_divisions=20)
FINE = MeshLevel("fine", circumferential_divisions=32, wall_divisions=4, length_divisions=40)

MESH_LEVELS = (COARSE, MEDIUM, FINE)
