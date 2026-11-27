"""CalculiX input deck for the solid I-beam in torsion: a structured C3D20R mesh, a torque
through a distributing *COUPLING at the tip, and output.

Axes: x along the beam (root face at x = 0, tip face at x = L), y vertical, z across the flange
width. The section centroid, which is also the shear centre, lies on the x axis. The torque acts
about +x by the right-hand rule.

The mesh lives on a lattice that holds every corner and midside position: an axis with n
elements has 2n + 1 lattice lines. A node is identified by its lattice index (i, j, k).
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from itertools import pairwise

from benchmark_parameters import BenchmarkParameters, MeshLevel

ROOT_FACE = "ROOT"
TIP_FACE = "TIPFACE"
TIP_SURFACE = "TIPSURF"
REFERENCE_NODE = "REFNODE"
TOP_FLANGE_CENTRE_LINE = "TOPLINE"
BOTTOM_FLANGE_CENTRE_LINE = "BOTLINE"
FLANGE_TIP_EDGES = ("TIPTOPNZ", "TIPTOPPZ", "TIPBOTNZ", "TIPBOTPZ")
"""The flange-tip edges at x = L/4 through the flange thickness: top flange at z = −b/2 and
+b/2, then bottom flange at z = −b/2 and +b/2."""
MIDSPAN_FLANGE_SURFACES = ("MIDTOPSURF", "MIDBOTSURF")
"""The top and bottom flange outer surface nodes at x = L/2 at the centres of the two flange
outstands, z = ±(b/2 + t_w/2)/2, away from the web."""
QUARTER_SPAN_FLANGES = ("QTOPFLANGE", "QBOTFLANGE")
"""Every node of the top and of the bottom flange at x = L/4, across the width and through
the thickness, for the figures."""
TOP_FLANGE_TIP_LINE = "TOPNZLINE"
"""The top flange-tip edge at z = −b/2 along the whole length, through the flange thickness,
for the figures."""
ALL_ELEMENTS = "EALL"
TIP_FACE_LABEL = "S4"
"""The C3D20 face through local nodes 2, 6, 7 and 3, which is the element's +x face."""

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
    tip = 2 * level.length_divisions
    quarter_span = tip // 4
    nf = level.flange_thickness_divisions
    top_surface = 2 * (2 * nf + level.web_height_divisions)
    top_mid_plane = top_surface - nf
    flange_edges = (0, 10 * nf)
    outstand_centres = (2 * nf, 8 * nf)

    def in_web_footprint(k: int) -> bool:
        return 4 * nf <= k <= 6 * nf

    def in_top_flange(j: int) -> bool:
        return j >= top_surface - 2 * nf

    def in_bottom_flange(j: int) -> bool:
        return j <= 2 * nf

    def flange_tip_edge(in_flange: Callable[[int], bool], k_edge: int) -> tuple[int, ...]:
        return mesh.nodes_where(lambda i, j, k: i == quarter_span and in_flange(j) and k == k_edge)

    def quarter_span_flange(in_flange: Callable[[int], bool]) -> tuple[int, ...]:
        return mesh.nodes_where(lambda i, j, k: i == quarter_span and in_flange(j))

    def midspan_surface(j_surface: int) -> tuple[int, ...]:
        return mesh.nodes_where(
            lambda i, j, k: i == tip // 2 and j == j_surface and k in outstand_centres
        )

    node_sets = {
        ROOT_FACE: mesh.nodes_where(lambda i, j, k: i == 0),
        TIP_FACE: mesh.nodes_where(lambda i, j, k: i == tip),
        REFERENCE_NODE: (reference_node,),
        TOP_FLANGE_CENTRE_LINE: mesh.nodes_where(
            lambda i, j, k: j == top_mid_plane and in_web_footprint(k)
        ),
        BOTTOM_FLANGE_CENTRE_LINE: mesh.nodes_where(
            lambda i, j, k: j == nf and in_web_footprint(k)
        ),
        MIDSPAN_FLANGE_SURFACES[0]: midspan_surface(top_surface),
        MIDSPAN_FLANGE_SURFACES[1]: midspan_surface(0),
        QUARTER_SPAN_FLANGES[0]: quarter_span_flange(in_top_flange),
        QUARTER_SPAN_FLANGES[1]: quarter_span_flange(in_bottom_flange),
        TOP_FLANGE_TIP_LINE: mesh.nodes_where(
            lambda i, j, k: in_top_flange(j) and k == flange_edges[0]
        ),
    }
    tip_edges = [
        flange_tip_edge(in_flange, k_edge)
        for in_flange in (in_top_flange, in_bottom_flange)
        for k_edge in flange_edges
    ]
    node_sets.update(zip(FLANGE_TIP_EDGES, tip_edges, strict=True))
    tip_elements = [eid for eid, (i, _, _) in enumerate(mesh.cell_origins, start=1) if i == tip - 2]

    lines = ["*HEADING", f"Solid I-beam in torsion, mesh level {level.name}", "*NODE, NSET=NALL"]
    lines += [f"{nid}, {x!r}, {y!r}, {z!r}" for nid, (x, y, z) in mesh.coordinates()]
    lines += ["*NODE", f"{reference_node}, {params.length!r}, 0.0, 0.0"]
    lines.append(f"*ELEMENT, TYPE=C3D20R, ELSET={ALL_ELEMENTS}")
    for eid, nodes in enumerate(mesh.elements, start=1):
        ids = [str(eid), *map(str, nodes)]
        lines += [", ".join(ids[:16]) + ",", ", ".join(ids[16:])]
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
        f"*SURFACE, NAME={TIP_SURFACE}, TYPE=ELEMENT",
        *(f"{eid}, {TIP_FACE_LABEL}" for eid in tip_elements),
        f"*COUPLING, REF NODE={reference_node}, SURFACE={TIP_SURFACE}, CONSTRAINT NAME=TORQUE",
        "*DISTRIBUTING",
        "1, 6",
        "*STEP",
        "*STATIC",
        "*CLOAD",
        f"{REFERENCE_NODE}, 4, {params.torque!r}",
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
    counts = {
        "flange_thickness_divisions": level.flange_thickness_divisions,
        "web_height_divisions": level.web_height_divisions,
        "length_divisions": level.length_divisions,
    }
    for name, count in counts.items():
        if count < 1:
            raise ValueError(f"{name} must be at least 1, got {count}")
    if level.length_divisions % 2:
        raise ValueError(
            "length_divisions must be even so that x = L/2 and L/4 fall on lattice lines, "
            f"got {level.length_divisions}"
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

        self.cell_origins = [
            (2 * cx, 2 * cy, 2 * cz)
            for cx in range(level.length_divisions)
            for cy in range(2 * nf + nw)
            for cz in range(5 * nf)
            if is_solid(cy, cz)
        ]
        element_indices = [
            [(i + di, j + dj, k + dk) for di, dj, dk in C3D20_OFFSETS]
            for i, j, k in self.cell_origins
        ]
        used = sorted({index for element in element_indices for index in element})
        self.node_ids: dict[Index, int] = {index: n for n, index in enumerate(used, start=1)}
        self.elements = [[self.node_ids[index] for index in e] for e in element_indices]

    def position(self, index: Index) -> tuple[float, float, float]:
        i, j, k = index
        return self.x[i], self.y[j], self.z[k]

    def coordinates(self) -> Iterable[tuple[int, tuple[float, float, float]]]:
        return ((nid, self.position(index)) for index, nid in self.node_ids.items())

    def nodes_where(self, predicate: Callable[[int, int, int], bool]) -> tuple[int, ...]:
        """Node ids whose lattice index (i, j, k) satisfies the predicate."""
        return tuple(nid for index, nid in self.node_ids.items() if predicate(*index))


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
