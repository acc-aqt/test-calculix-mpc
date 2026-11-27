"""CalculiX input deck for the LE10 thick plate: a mapped C3D20R or C3D20 mesh of the quarter
elliptic annulus, the LE10 supports, a pressure on the top face, and output.

Axes: x and y in the plane of the plate, z through the thickness with the mid-plane at z = 0.
The hole edge is the inner ellipse, point D is at (a_i, 0, +t/2) and A at (0, b_i, +t/2).

The mesh lives on a lattice that holds every corner and midside position: a direction with n
elements has 2n + 1 lattice lines. A node is identified by its lattice index (a, t, k): across
the annulus from the inner to the outer ellipse, around it from the x axis (θ = 0) to the y axis
(θ = π/2), and through the thickness from the bottom face to the top face. The node at (a, t, k)
sits on the straight line joining the two ellipses at parametric angle θ, (a cos θ, b sin θ), so
midside nodes on the curved edges lie exactly on the ellipses.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from benchmark_parameters import BenchmarkParameters, MeshLevel

C3D20R = "C3D20R"
"""20-node brick, reduced integration."""
C3D20 = "C3D20"
"""20-node brick, full integration: solved for information only."""
ELEMENT_TYPES = (C3D20R, C3D20)
VERDICT_ELEMENT_TYPE = C3D20R
"""The element type whose fine level decides the LE10 verdict."""

Y0_FACE = "YSYMM"
X0_FACE = "XSYMM"
OUTER_FACE = "OUTER"
LINE_EE = "LINEEE"
"""The outer face at z = 0, corner and midside nodes."""
POINT_D = "POINTD"
HOLE_EDGE = "HOLEEDGE"
"""The top-face hole edge from D (θ = 0) to A (θ = π/2)."""
THICKNESS_LINE_AT_D = "THICKD"
"""Through the thickness at x = a_i, y = 0, from the bottom face to D."""
ELEMENT_AT_D = "ELEMD"
"""The one element with a corner at D, whose integration points are printed to the .dat."""
TOP_SURFACE = "TOPSURF"
ALL_ELEMENTS = "EALL"
TOP_FACE_LABEL = "S2"
"""The C3D20 face through local nodes 5, 8, 7 and 6, which is the element's +k face."""

# C3D20 local nodes as lattice offsets within one element, in CalculiX order: corners 1-4 on the
# dk = 0 face and 5-8 on the dk = 2 face, both counter-clockwise seen from +k; midsides 9-12 and
# 13-16 on the edges of those faces; midsides 17-20 on the edges joining them.
_CORNERS = [(0, 0, 0), (2, 0, 0), (2, 2, 0), (0, 2, 0), (0, 0, 2), (2, 0, 2), (2, 2, 2), (0, 2, 2)]
_FACE_EDGES = [(1, 2), (2, 3), (3, 4), (4, 1)]
_EDGES = _FACE_EDGES + [(m + 4, n + 4) for m, n in _FACE_EDGES] + [(n, n + 4) for n in range(1, 5)]
C3D20_OFFSETS = _CORNERS + [
    tuple((p + q) // 2 for p, q in zip(_CORNERS[m - 1], _CORNERS[n - 1], strict=True))
    for m, n in _EDGES
]

_NATURAL = np.array(C3D20_OFFSETS, dtype=float) - 1.0
"""Natural coordinates (ξ, η, ζ) in [−1, 1]³ of the 20 local nodes."""
_GAUSS_POINTS = (-math.sqrt(0.6), 0.0, math.sqrt(0.6))
_GAUSS_WEIGHTS = (5 / 9, 8 / 9, 5 / 9)

Index = tuple[int, int, int]
Point = tuple[float, float, float]


@dataclass(frozen=True)
class Deck:
    text: str
    nodes: dict[int, Point]
    elements: tuple[tuple[int, ...], ...]
    """Node ids of each element in CalculiX C3D20 order; element ids count from 1."""
    node_sets: dict[str, tuple[int, ...]]

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def element_count(self) -> int:
        return len(self.elements)


def generate_deck(
    params: BenchmarkParameters, level: MeshLevel, element_type: str = C3D20R
) -> Deck:
    _check_divisions(level)
    mesh = _Mesh(params, level)
    outer = 2 * level.across_divisions
    y_axis = 2 * level.around_divisions
    top = 2 * level.thickness_divisions
    mid = level.thickness_divisions

    node_sets = {
        Y0_FACE: mesh.nodes_where(lambda a, t, k: t == 0),
        X0_FACE: mesh.nodes_where(lambda a, t, k: t == y_axis),
        OUTER_FACE: mesh.nodes_where(lambda a, t, k: a == outer),
        LINE_EE: mesh.nodes_where(lambda a, t, k: a == outer and k == mid),
        POINT_D: mesh.nodes_where(lambda a, t, k: a == 0 and t == 0 and k == top),
        HOLE_EDGE: mesh.nodes_where(lambda a, t, k: a == 0 and k == top),
        THICKNESS_LINE_AT_D: mesh.nodes_where(lambda a, t, k: a == 0 and t == 0),
    }
    top_elements = mesh.elements_where(lambda a, t, k: k == top - 2)
    element_at_d = mesh.elements_where(lambda a, t, k: a == 0 and t == 0 and k == top - 2)

    lines = ["*HEADING", f"NAFEMS LE10 thick plate, mesh level {level.name}", "*NODE, NSET=NALL"]
    lines += [f"{nid}, {x!r}, {y!r}, {z!r}" for nid, (x, y, z) in mesh.nodes.items()]
    lines.append(f"*ELEMENT, TYPE={element_type}, ELSET={ALL_ELEMENTS}")
    for eid, nodes in enumerate(mesh.elements, start=1):
        ids = [str(eid), *map(str, nodes)]
        lines += [", ".join(ids[:16]) + ",", ", ".join(ids[16:])]
    for name, ids in node_sets.items():
        lines.append(f"*NSET, NSET={name}")
        lines += _wrap(ids)
    lines += [f"*ELSET, ELSET={ELEMENT_AT_D}", *_wrap(element_at_d)]
    m = params.material
    lines += [
        "*MATERIAL, NAME=STEEL",
        "*ELASTIC",
        f"{m.youngs_modulus!r}, {m.poissons_ratio!r}",
        f"*SOLID SECTION, ELSET={ALL_ELEMENTS}, MATERIAL=STEEL",
        "*BOUNDARY",
        f"{Y0_FACE}, 2, 2",
        f"{X0_FACE}, 1, 1",
        f"{OUTER_FACE}, 1, 2",
        f"{LINE_EE}, 3, 3",
        f"*SURFACE, NAME={TOP_SURFACE}, TYPE=ELEMENT",
        *(f"{eid}, {TOP_FACE_LABEL}" for eid in top_elements),
        "*STEP",
        "*STATIC",
        "*DLOAD",
        f"{TOP_SURFACE}, P, {params.pressure!r}",
        "*NODE FILE",
        "U",
        "*EL FILE",
        "S",
        f"*EL PRINT, ELSET={ELEMENT_AT_D}",
        "S, COORD",
        f"*NODE PRINT, NSET={LINE_EE}, TOTALS=ONLY",
        "RF",
        "*END STEP",
    ]
    return Deck(
        text="\n".join(lines) + "\n",
        nodes=mesh.nodes,
        elements=tuple(tuple(e) for e in mesh.elements),
        node_sets=node_sets,
    )


def mesh_volume(deck: Deck) -> float:
    """The volume of the deck's elements, integrated from their node positions with the
    20-node serendipity shape functions and 3×3×3 Gauss points, so curved edges count."""
    gradients = [
        (w1 * w2 * w3, _shape_gradients(np.array([p1, p2, p3])))
        for p1, w1 in zip(_GAUSS_POINTS, _GAUSS_WEIGHTS, strict=True)
        for p2, w2 in zip(_GAUSS_POINTS, _GAUSS_WEIGHTS, strict=True)
        for p3, w3 in zip(_GAUSS_POINTS, _GAUSS_WEIGHTS, strict=True)
    ]
    volume = 0.0
    for element in deck.elements:
        positions = np.array([deck.nodes[n] for n in element])
        volume += sum(weight * np.linalg.det(grad.T @ positions) for weight, grad in gradients)
    return float(volume)


def _shape_gradients(point: np.ndarray) -> np.ndarray:
    """∂N_i/∂(ξ, η, ζ) of the 20 serendipity shape functions at a natural point, shape (20, 3).

    A corner node at n = (±1, ±1, ±1) has N = ⅛ Π(1 + n_j x_j) · (n·x − 2); a midside node has
    N = ¼ Π f_j, with f_j = 1 − x_j² along its edge and 1 + n_j x_j across it.
    """
    gradients = np.zeros((20, 3))
    for i, n in enumerate(_NATURAL):
        if np.all(n != 0):
            linear = 1 + n * point
            for j in range(3):
                others = np.prod(np.delete(linear, j))
                gradients[i, j] = n[j] * others * (n @ point + linear[j] - 2) / 8
        else:
            factors = np.where(n == 0, 1 - point**2, 1 + n * point)
            derivatives = np.where(n == 0, -2 * point, n)
            for j in range(3):
                gradients[i, j] = derivatives[j] * np.prod(np.delete(factors, j)) / 4
    return gradients


def _check_divisions(level: MeshLevel) -> None:
    counts = {
        "around_divisions": level.around_divisions,
        "across_divisions": level.across_divisions,
        "thickness_divisions": level.thickness_divisions,
    }
    for name, count in counts.items():
        if count < 1:
            raise ValueError(f"{name} must be at least 1, got {count}")
    if level.thickness_divisions % 2:
        raise ValueError(
            "thickness_divisions must be even so that line EE′ (z = 0) has corner and midside "
            f"nodes, got {level.thickness_divisions}"
        )


class _Mesh:
    def __init__(self, params: BenchmarkParameters, level: MeshLevel):
        self.cell_origins = [
            (2 * ca, 2 * ct, 2 * ck)
            for ca in range(level.across_divisions)
            for ct in range(level.around_divisions)
            for ck in range(level.thickness_divisions)
        ]
        element_indices = [
            [(a + da, t + dt, k + dk) for da, dt, dk in C3D20_OFFSETS]
            for a, t, k in self.cell_origins
        ]
        used = sorted({index for element in element_indices for index in element})
        self.node_ids: dict[Index, int] = {index: n for n, index in enumerate(used, start=1)}
        self.elements = [[self.node_ids[index] for index in e] for e in element_indices]
        self.nodes = {nid: _position(params, level, index) for index, nid in self.node_ids.items()}

    def nodes_where(self, predicate: Callable[[int, int, int], bool]) -> tuple[int, ...]:
        """Node ids whose lattice index (a, t, k) satisfies the predicate."""
        return tuple(nid for index, nid in self.node_ids.items() if predicate(*index))

    def elements_where(self, predicate: Callable[[int, int, int], bool]) -> tuple[int, ...]:
        """Element ids whose lowest lattice index (a, t, k) satisfies the predicate."""
        return tuple(
            eid for eid, origin in enumerate(self.cell_origins, start=1) if predicate(*origin)
        )


def _position(params: BenchmarkParameters, level: MeshLevel, index: Index) -> Point:
    a, t, k = index
    s = a / (2 * level.across_divisions)
    theta = math.pi / 2 * t / (2 * level.around_divisions)
    semi_x = (1 - s) * params.inner.semi_axis_x + s * params.outer.semi_axis_x
    semi_y = (1 - s) * params.inner.semi_axis_y + s * params.outer.semi_axis_y
    z = params.thickness * (k / (2 * level.thickness_divisions) - 0.5)
    return _snap(semi_x * math.cos(theta)), _snap(semi_y * math.sin(theta)), _snap(z)


def _snap(value: float) -> float:
    return 0.0 if abs(value) < 1e-9 else value


def _wrap(ids: tuple[int, ...], per_line: int = 16) -> list[str]:
    return [", ".join(map(str, ids[n : n + per_line])) for n in range(0, len(ids), per_line)]
