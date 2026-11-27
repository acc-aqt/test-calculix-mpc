import subprocess

import pytest

from benchmark_parameters import COARSE, LE10, MeshLevel
from deck import HOLE_EDGE, LINE_EE, POINT_D, THICKNESS_LINE_AT_D, generate_deck
from runner import JOB_NAME, find_ccx

CCX = find_ccx()

needs_ccx = pytest.mark.skipif(
    CCX is None,
    reason="ccx not found: set CCX or run inside the calculix-bench environment",
)

# C3D20 midside node position (1-based) to the two corners of its edge, in CalculiX order.
C3D20_EDGES = {
    9: (1, 2), 10: (2, 3), 11: (3, 4), 12: (4, 1),
    13: (5, 6), 14: (6, 7), 15: (7, 8), 16: (8, 5),
    17: (1, 5), 18: (2, 6), 19: (3, 7), 20: (4, 8),
}  # fmt: skip


@pytest.fixture(scope="module")
def coarse_deck():
    return generate_deck(LE10, COARSE)


def on_ellipse(point, ellipse):
    x, y, _ = point
    return (x / ellipse.semi_axis_x) ** 2 + (y / ellipse.semi_axis_y) ** 2 == pytest.approx(
        1.0, abs=1e-12
    )


def coordinates(deck, name):
    return [deck.nodes[n] for n in deck.node_sets[name]]


def test_every_midside_node_on_a_curved_edge_lies_on_its_ellipse(coarse_deck):
    checked = 0
    for element in coarse_deck.elements:
        for midside, (m, n) in C3D20_EDGES.items():
            ends = (coarse_deck.nodes[element[m - 1]], coarse_deck.nodes[element[n - 1]])
            middle = coarse_deck.nodes[element[midside - 1]]
            for ellipse in (LE10.inner, LE10.outer):
                curved = ends[0][:2] != ends[1][:2]
                if curved and all(on_ellipse(end, ellipse) for end in ends):
                    assert on_ellipse(middle, ellipse)
                    checked += 1
    # 6 elements around x 2 through the thickness, 2 curved edges each, on each ellipse.
    assert checked == 48


def test_point_d_is_on_the_hole_edge_on_the_x_axis_on_the_loaded_face(coarse_deck):
    assert coordinates(coarse_deck, POINT_D) == [(2000.0, 0.0, 300.0)]


def test_line_ee_lies_on_the_outer_ellipse_at_mid_thickness_with_its_midside_nodes(coarse_deck):
    line = coordinates(coarse_deck, LINE_EE)
    assert len(line) == 2 * COARSE.around_divisions + 1
    assert all(on_ellipse(p, LE10.outer) and p[2] == 0.0 for p in line)
    assert {(3250.0, 0.0, 0.0), (0.0, 2750.0, 0.0)} <= set(line)


def test_hole_edge_runs_from_d_to_a_on_the_inner_ellipse_on_the_loaded_face(coarse_deck):
    edge = coordinates(coarse_deck, HOLE_EDGE)
    assert len(edge) == 2 * COARSE.around_divisions + 1
    assert all(on_ellipse(p, LE10.inner) and p[2] == 300.0 for p in edge)
    assert {(2000.0, 0.0, 300.0), (0.0, 1000.0, 300.0)} <= set(edge)


def test_thickness_line_at_d_runs_through_the_plate_at_x_2000_y_0(coarse_deck):
    line = coordinates(coarse_deck, THICKNESS_LINE_AT_D)
    assert all(p[:2] == (2000.0, 0.0) for p in line)
    assert sorted(p[2] for p in line) == [-300.0, -150.0, 0.0, 150.0, 300.0]


def test_odd_thickness_divisions_are_rejected_because_ee_needs_a_node_line_at_z_0():
    with pytest.raises(ValueError, match="thickness_divisions must be even"):
        generate_deck(LE10, MeshLevel("bad", 6, 4, 3))


@needs_ccx
def test_coarse_deck_solves_without_errors_or_warnings(coarse_deck, tmp_path):
    (tmp_path / f"{JOB_NAME}.inp").write_text(coarse_deck.text)
    completed = subprocess.run(
        [str(CCX), "-i", JOB_NAME], cwd=tmp_path, capture_output=True, text=True, check=False
    )
    output = completed.stdout + completed.stderr
    assert completed.returncode == 0
    assert "Job finished" in output
    assert "ERROR" not in output.upper()
    assert "WARNING" not in output.upper()
