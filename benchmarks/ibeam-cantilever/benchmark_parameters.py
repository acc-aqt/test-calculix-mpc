"""The benchmark case in one place. Units: N, mm, MPa.

Override a value with dataclasses.replace, e.g.
    replace(IPE200_CANTILEVER, length=4000.0)
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ISection:
    """Doubly symmetric I-section without fillet radii."""

    height: float
    flange_width: float
    web_thickness: float
    flange_thickness: float


@dataclass(frozen=True)
class Material:
    youngs_modulus: float
    poissons_ratio: float


@dataclass(frozen=True)
class BenchmarkParameters:
    section: ISection
    length: float
    material: Material
    tip_load: float
    """Magnitude of the tip load; it acts in -y."""


IPE200_CANTILEVER = BenchmarkParameters(
    section=ISection(height=200.0, flange_width=100.0, web_thickness=5.6, flange_thickness=8.5),
    length=3000.0,
    material=Material(youngs_modulus=210_000.0, poissons_ratio=0.3),
    tip_load=10_000.0,
)
