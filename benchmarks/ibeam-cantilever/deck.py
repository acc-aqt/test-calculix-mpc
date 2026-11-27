"""CalculiX input deck for the solid I-beam: a structured C3D20R mesh plus loads and output.

Axes: x along the beam (root face at x = 0, tip face at x = L), y vertical (load in -y),
z across the flange width. The section centroid lies on the x axis.

The mesh lives on a lattice that holds every corner and midside position: an axis with n
elements has 2n + 1 lattice lines. A node is identified by its lattice index (i, j, k).
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from itertools import pairwise

from benchmark_parameters import BenchmarkParameters, MeshLevel

ROOT_FACE = "ROOT"
TIP_FACE = "TIPFACE"
REFERENCE_NODE = "REFNODE"
WEB_CENTRELINE_TIP_NODE = "WEBTIP"
MIDSPAN_TOP_FLANGE = "MIDTOP"
MIDSPAN_BOTTOM_FLANGE = "MIDBOT"
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
    if level.length_divisions % 2:
        raise ValueError("length_divisions must be even so that x = L/2 falls on a node plane")
    mesh = _Mesh(params, level)
    reference_node = len(mesh.node_ids) + 1
    coupling_element = len(mesh.elements) + 1
    length = params.length
    midspan = length / 2
    half_h = params.section.height / 2

    node_sets = {
        ROOT_FACE: mesh.nodes_where(lambda x, y, z: x == 0.0),
        TIP_FACE: mesh.nodes_where(lambda x, y, z: x == length),
        WEB_CENTRELINE_TIP_NODE: mesh.nodes_where(lambda x, y, z: (x, y, z) == (length, 0.0, 0.0)),
        REFERENCE_NODE: (reference_node,),
        MIDSPAN_TOP_FLANGE: mesh.nodes_where(lambda x, y, z: (x, y) == (midspan, half_h)),
        MIDSPAN_BOTTOM_FLANGE: mesh.nodes_where(lambda x, y, z: (x, y) == (midspan, -half_h)),
    }
    if len(node_sets[WEB_CENTRELINE_TIP_NODE]) != 1:
        raise ValueError("mesh has no node at the tip-face centroid")

    lines = ["*HEADING", f"Solid I-beam cantilever, mesh level {level.name}", "*NODE, NSET=NALL"]
    lines += [f"{nid}, {x!r}, {y!r}, {z!r}" for nid, (x, y, z) in mesh.coordinates()]
    lines += ["*NODE", f"{reference_node}, {length!r}, 0.0, 0.0"]
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


class _Mesh:
    def __init__(self, params: BenchmarkParameters, level: MeshLevel):
        s = params.section
        nf = level.flange_thickness_divisions
        nw = level.web_height_divisions
        half_h, half_b, half_tw = s.height / 2, s.flange_width / 2, s.web_thickness / 2
        web_top = half_h - s.flange_thickness
        self.x = _lattice([(0.0, params.length, level.length_divisions)])
        self.y = _lattice([(-half_h, -web_top, nf), (-web_top, web_top, nw), (web_top, half_h, nf)])
        self.z = _lattice(
            [(-half_b, -half_tw, 2 * nf), (-half_tw, half_tw, nf), (half_tw, half_b, 2 * nf)]
        )

        def is_solid(cy: int, cz: int) -> bool:
            in_flange = cy < nf or cy >= nf + nw
            in_web = 2 * nf <= cz < 3 * nf
            return in_flange or in_web

        cells = [
            (2 * cx, 2 * cy, 2 * cz)
            for cx in range(level.length_divisions)
            for cy in range(2 * nf + nw)
            for cz in range(5 * nf)
            if is_solid(cy, cz)
        ]
        element_indices = [
            [(i + di, j + dj, k + dk) for di, dj, dk in C3D20_OFFSETS] for i, j, k in cells
        ]
        used = sorted({index for element in element_indices for index in element})
        self.node_ids: dict[Index, int] = {index: n for n, index in enumerate(used, start=1)}
        self.elements = [[self.node_ids[index] for index in e] for e in element_indices]

    def position(self, index: Index) -> tuple[float, float, float]:
        i, j, k = index
        return self.x[i], self.y[j], self.z[k]

    def coordinates(self) -> Iterable[tuple[int, tuple[float, float, float]]]:
        return ((nid, self.position(index)) for index, nid in self.node_ids.items())

    def nodes_where(self, predicate: Callable[[float, float, float], bool]) -> tuple[int, ...]:
        return tuple(nid for nid, xyz in self.coordinates() if predicate(*xyz))


def _lattice(segments: list[tuple[float, float, int]]) -> list[float]:
    """Corner and midside coordinates along one axis, from (start, end, elements) segments."""
    corners: list[float] = [segments[0][0]]
    for start, end, n in segments:
        corners += [start + (end - start) * e / n for e in range(1, n)] + [end]
    points = [corners[0]]
    for a, b in pairwise(corners):
        points += [(a + b) / 2, b]
    return [0.0 if abs(p) < 1e-9 else p for p in points]


def _wrap(ids: tuple[int, ...], per_line: int = 16) -> list[str]:
    return [", ".join(map(str, ids[n : n + per_line])) for n in range(0, len(ids), per_line)]
