"""CalculiX input deck for the solid tube: a mapped C3D20R mesh plus loads and output.

Axes: x along the tube (root face at x = 0, tip face at x = L), y vertical (load in -y), z
horizontal. The section centroid lies on the x axis.

The mesh lives on a lattice over (x, r, θ) that holds every corner and midside position: an
axis with n elements has 2n + 1 lattice lines, except θ, whose 2n lines wrap around so that the
seam shares nodes. A node is identified by its lattice index (i, j, k) and sits at
x, y = r cos θ, z = r sin θ, with θ = 0 at the top fibre. Midside nodes therefore lie on the
true arcs. (x, r, θ) is right-handed, so the C3D20 offsets give positive Jacobians.
"""

import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from benchmark_parameters import BenchmarkParameters, MeshLevel

ROOT_FACE = "ROOT"
TIP_FACE = "TIPFACE"
REFERENCE_NODE = "REFNODE"
MIDSPAN_OUTER_SURFACE = "MIDOUTER"
MIDSPAN_TOP_FIBRE = "MIDTOP"
MIDSPAN_BOTTOM_FIBRE = "MIDBOT"
ALL_ELEMENTS = "EALL"

# C3D20 local nodes as lattice offsets (dx, dy, dz) within one element, in CalculiX order:
# corners 1-4 on the dz = 0 face and 5-8 on the dz = 2 face, both counter-clockwise seen from +z;
# midsides 9-12 and 13-16 on the edges of those faces; midsides 17-20 on the edges joining them.
_CORNERS = [(0, 0, 0), (2, 0, 0), (2, 2, 0), (0, 2, 0), (0, 0, 2), (2, 0, 2), (2, 2, 2), (0, 2, 2)]
_FACE_EDGES = [(1, 2), (2, 3), (3, 4), (4, 1)]
_EDGES = _FACE_EDGES + [(m + 4, n + 4) for m, n in _FACE_EDGES] + [(n, n + 4) for n in range(1, 5)]
C3D20_OFFSETS = _CORNERS + [
    tuple((a + b) // 2 for a, b in zip(_CORNERS[m - 1], _CORNERS[n - 1], strict=True))
    for m, n in _EDGES
]

Index = tuple[int, int, int]


@dataclass(frozen=True)
class Deck:
    text: str
    node_count: int
    """Mesh nodes plus the reference node."""
    element_count: int
    """Solid elements only."""
    node_sets: dict[str, tuple[int, ...]]


def generate_deck(params: BenchmarkParameters, level: MeshLevel) -> Deck:
    _check_divisions(level)
    mesh = _Mesh(params, level)
    reference_node = len(mesh.node_ids) + 1
    coupling_element = len(mesh.elements) + 1
    tip, mid = 2 * level.length_divisions, level.length_divisions
    outer, bottom = 2 * level.wall_divisions, level.circumferential_divisions

    node_sets = {
        ROOT_FACE: mesh.nodes_where(lambda i, j, k: i == 0),
        TIP_FACE: mesh.nodes_where(lambda i, j, k: i == tip),
        REFERENCE_NODE: (reference_node,),
        MIDSPAN_OUTER_SURFACE: mesh.nodes_where(lambda i, j, k: (i, j) == (mid, outer)),
        MIDSPAN_TOP_FIBRE: mesh.nodes_where(lambda i, j, k: (i, j, k) == (mid, outer, 0)),
        MIDSPAN_BOTTOM_FIBRE: mesh.nodes_where(lambda i, j, k: (i, j, k) == (mid, outer, bottom)),
    }

    lines = ["*HEADING", f"Solid tube cantilever, mesh level {level.name}", "*NODE, NSET=NALL"]
    lines += [f"{nid}, {_coordinates(xyz)}" for nid, xyz in mesh.coordinates()]
    lines += ["*NODE", f"{reference_node}, {_coordinates((params.length, 0.0, 0.0))}"]
    lines.append(f"*ELEMENT, TYPE=C3D20R, ELSET={ALL_ELEMENTS}")
    for eid, nodes in enumerate(mesh.elements, start=1):
        ids = [str(eid), *map(str, nodes)]
        lines += [", ".join(ids[:16]) + ",", ", ".join(ids[16:])]
    lines += ["*ELEMENT, TYPE=DCOUP3D, ELSET=ECOUP", f"{coupling_element}, {reference_node}"]
    for name, ids in node_sets.items():
        lines.append(f"*NSET, NSET={name}")
        lines += _wrap(ids)
    m = params.material
    lines += [
        "*MATERIAL, NAME=STEEL",
        "*ELASTIC",
        f"{m.youngs_modulus!r}, {m.poissons_ratio!r}",
        f"*SOLID SECTION, ELSET={ALL_ELEMENTS}, MATERIAL=STEEL",
        "*BOUNDARY",
        f"{ROOT_FACE}, 1, 3",
        "*DISTRIBUTING COUPLING, ELSET=ECOUP",
        f"{TIP_FACE}, 1.0",
        "*STEP",
        "*STATIC",
        "*CLOAD",
        f"{REFERENCE_NODE}, 2, {-params.tip_load!r}",
        "*NODE FILE",
        "U",
        "*EL FILE",
        "S",
        f"*NODE PRINT, NSET={REFERENCE_NODE}",
        "U",
        "*END STEP",
    ]
    return Deck(
        text="\n".join(lines) + "\n",
        node_count=reference_node,
        element_count=len(mesh.elements),
        node_sets=node_sets,
    )


def _check_divisions(level: MeshLevel) -> None:
    if level.circumferential_divisions < 4 or level.circumferential_divisions % 4:
        raise ValueError(
            "circumferential_divisions must be a multiple of 4 so that 0°, 90°, 180° and 270° "
            f"fall on nodes, got {level.circumferential_divisions}"
        )
    if level.length_divisions < 2 or level.length_divisions % 2:
        raise ValueError(
            "length_divisions must be even so that x = L/2 falls on a node plane, "
            f"got {level.length_divisions}"
        )


class _Mesh:
    def __init__(self, params: BenchmarkParameters, level: MeshLevel):
        s = params.section
        nx, nr, nt = level.length_divisions, level.wall_divisions, level.circumferential_divisions
        self.x = _lattice(0.0, params.length, nx)
        self.r = _lattice(s.inner_radius, s.outer_radius, nr)
        self.theta = _lattice(0.0, 2 * math.pi, nt)[:-1]
        wrap = len(self.theta)

        cells = [
            (2 * cx, 2 * cr, 2 * ct) for cx in range(nx) for cr in range(nr) for ct in range(nt)
        ]
        element_indices = [
            [(i + di, j + dj, (k + dk) % wrap) for di, dj, dk in C3D20_OFFSETS] for i, j, k in cells
        ]
        used = sorted({index for element in element_indices for index in element})
        self.node_ids: dict[Index, int] = {index: n for n, index in enumerate(used, start=1)}
        self.elements = [[self.node_ids[index] for index in e] for e in element_indices]

    def position(self, index: Index) -> tuple[float, float, float]:
        i, j, k = index
        r, theta = self.r[j], self.theta[k]
        return self.x[i], r * math.cos(theta), r * math.sin(theta)

    def coordinates(self) -> Iterable[tuple[int, tuple[float, float, float]]]:
        return ((nid, self.position(index)) for index, nid in self.node_ids.items())

    def nodes_where(self, predicate: Callable[[int, int, int], bool]) -> tuple[int, ...]:
        return tuple(nid for index, nid in self.node_ids.items() if predicate(*index))


def _lattice(start: float, end: float, elements: int) -> list[float]:
    """Corner and midside coordinates of `elements` equal elements from start to end."""
    return [start + (end - start) * n / (2 * elements) for n in range(2 * elements + 1)]


def _coordinates(xyz: tuple[float, float, float]) -> str:
    """At most 14 significant digits and round-off below 1e-9 as 0: ccx rejects full-precision
    values such as 4.6628426877535476e-15 from cos(90°)."""
    return ", ".join("0.0" if abs(v) < 1e-9 else f"{v:.14g}" for v in xyz)


def _wrap(ids: tuple[int, ...], per_line: int = 16) -> list[str]:
    return [", ".join(map(str, ids[n : n + per_line])) for n in range(0, len(ids), per_line)]
