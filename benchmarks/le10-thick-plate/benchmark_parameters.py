"""The benchmark case in one place. Units: N, mm, MPa.

Override a value with dataclasses.replace, e.g.
    replace(LE10, pressure=2.0)
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Ellipse:
    """An ellipse centred on the origin, x²/a² + y²/b² = 1."""

    semi_axis_x: float
    semi_axis_y: float


@dataclass(frozen=True)
class Material:
    youngs_modulus: float
    poissons_ratio: float


@dataclass(frozen=True)
class BenchmarkParameters:
    inner: Ellipse
    """The hole edge."""
    outer: Ellipse
    thickness: float
    """Centred on the mid-plane, so z runs from −thickness/2 to +thickness/2."""
    material: Material
    pressure: float
    """Uniform pressure on the top face (z = +thickness/2), pushing down."""


LE10 = BenchmarkParameters(
    inner=Ellipse(semi_axis_x=2000.0, semi_axis_y=1000.0),
    outer=Ellipse(semi_axis_x=3250.0, semi_axis_y=2750.0),
    thickness=600.0,
    material=Material(youngs_modulus=210_000.0, poissons_ratio=0.3),
    pressure=1.0,
)


@dataclass(frozen=True)
class MeshLevel:
    """Element counts around the annulus, across it and through the thickness."""

    name: str
    around_divisions: int
    across_divisions: int
    thickness_divisions: int

    @property
    def label(self) -> str:
        """Name and divisions, e.g. "coarse 6×4×2"."""
        return (
            f"{self.name} {self.around_divisions}×{self.across_divisions}×"
            f"{self.thickness_divisions}"
        )


COARSE = MeshLevel("coarse", around_divisions=6, across_divisions=4, thickness_divisions=2)
MEDIUM = MeshLevel("medium", around_divisions=12, across_divisions=8, thickness_divisions=4)
FINE = MeshLevel("fine", around_divisions=24, across_divisions=16, thickness_divisions=8)

MESH_LEVELS = (COARSE, MEDIUM, FINE)
