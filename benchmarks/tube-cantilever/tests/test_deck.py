import math
import subprocess

import pytest

from benchmark_parameters import CHS168_CANTILEVER, COARSE
from deck import (
    MIDSPAN_BOTTOM_FIBRE,
    MIDSPAN_OUTER_SURFACE,
    MIDSPAN_TOP_FIBRE,
    ROOT_FACE,
    TIP_FACE,
    generate_deck,
)
from frd import read_frd
from runner import JOB_NAME, find_ccx, run_ccx

CCX = find_ccx()

pytestmark = pytest.mark.skipif(
    CCX is None,
    reason="ccx not found: set CCX or run inside the calculix-bench environment",
)


@pytest.fixture(scope="module")
def coarse_deck():
    return generate_deck(CHS168_CANTILEVER, COARSE)


@pytest.fixture(scope="module")
def coarse_frd(coarse_deck, tmp_path_factory):
    job_dir = tmp_path_factory.mktemp("work") / COARSE.name
    return read_frd(run_ccx(coarse_deck.text, job_dir, CCX))


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


def test_coarse_mesh_has_80_twenty_node_elements_and_600_solid_nodes(coarse_deck, coarse_frd):
    # 8 around x 1 through the wall x 10 along. Each of the 11 corner x-planes holds 16 nodes on
    # the inner and on the outer circle plus 8 mid-wall nodes (40); each of the 10 midside
    # x-planes holds 8 on each circle (16). 11 x 40 + 10 x 16 = 600, plus the reference node.
    assert coarse_deck.element_count == len(coarse_frd.elements) == 80
    assert all(len(connectivity) == 20 for connectivity in coarse_frd.elements.values())
    assert len(coarse_frd.nodes) == 600
    assert coarse_deck.node_count == 601


def test_tube_closes_on_itself_without_a_seam(coarse_frd):
    rounded = {tuple(round(c, 6) for c in xyz) for xyz in coarse_frd.nodes.values()}
    assert len(rounded) == len(coarse_frd.nodes)


def test_midside_nodes_lie_on_the_true_circles(coarse_deck, coarse_frd):
    # Every midspan outer-surface node, corner or midside, is at r_o = 84.15 from the axis (to
    # the .frd print precision); a midside at the chord midpoint would be at 0.92 r_o.
    nodes = coarse_deck.node_sets[MIDSPAN_OUTER_SURFACE]
    assert len(nodes) == 16
    for n in nodes:
        x, y, z = coarse_frd.nodes[n]
        assert x == pytest.approx(500.0)
        assert math.hypot(y, z) == pytest.approx(84.15, rel=1e-5)


def test_midspan_fibre_nodes_sit_at_the_top_and_bottom_of_the_outer_surface(
    coarse_deck, coarse_frd
):
    (top,) = coarse_deck.node_sets[MIDSPAN_TOP_FIBRE]
    (bottom,) = coarse_deck.node_sets[MIDSPAN_BOTTOM_FIBRE]
    assert coarse_frd.nodes[top] == pytest.approx((500.0, 84.15, 0.0))
    assert coarse_frd.nodes[bottom] == pytest.approx((500.0, -84.15, 0.0))


def test_root_face_is_fixed(coarse_deck, coarse_frd):
    displacements = coarse_frd.nodal_results["DISP"]
    for n in coarse_deck.node_sets[ROOT_FACE]:
        assert coarse_frd.nodes[n][0] == 0.0
        assert displacements[n] == pytest.approx((0.0, 0.0, 0.0), abs=1e-12)


def test_tip_face_nodes_lie_on_the_tip_plane(coarse_deck, coarse_frd):
    tip = coarse_deck.node_sets[TIP_FACE]
    assert all(coarse_frd.nodes[n][0] == pytest.approx(1000.0) for n in tip)
