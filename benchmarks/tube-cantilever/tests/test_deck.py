import math
import subprocess

import pytest

from benchmark_parameters import CHS168_CANTILEVER, COARSE, MeshLevel
from dat import read_printed_displacements
from deck import (
    MIDSPAN_BOTTOM_FIBRE,
    MIDSPAN_OUTER_SURFACE,
    MIDSPAN_TOP_FIBRE,
    REFERENCE_NODE,
    ROOT_FACE,
    TIP_FACE,
    generate_deck,
)
from frd import read_frd
from runner import JOB_NAME, CcxError, find_ccx, run_ccx

CCX = find_ccx()

needs_ccx = pytest.mark.skipif(
    CCX is None,
    reason="ccx not found: set CCX or run inside the calculix-bench environment",
)


@pytest.fixture(scope="module")
def coarse_deck():
    return generate_deck(CHS168_CANTILEVER, COARSE)


@pytest.fixture(scope="module")
def coarse_job(coarse_deck, tmp_path_factory):
    job_dir = tmp_path_factory.mktemp("work") / COARSE.name
    run_ccx(coarse_deck.text, job_dir, CCX)
    return job_dir


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


@needs_ccx
def test_coarse_reference_node_deflects_down_within_one_percent_of_timoshenko(
    coarse_deck, coarse_job
):
    # Timoshenko target with Cowper kappa: 1.28126 mm (see test_analytical.py).
    printed = read_printed_displacements(coarse_job / f"{JOB_NAME}.dat")[REFERENCE_NODE]
    (reference,) = coarse_deck.node_sets[REFERENCE_NODE]
    uy = printed[reference][1]
    assert uy < 0
    assert -uy == pytest.approx(1.28126, rel=0.01)


@pytest.fixture(scope="module")
def coarse_frd(coarse_job):
    return read_frd(coarse_job / f"{JOB_NAME}.frd")


@needs_ccx
def test_coarse_mesh_has_80_twenty_node_elements_and_600_solid_nodes(coarse_deck, coarse_frd):
    # 8 around x 1 through the wall x 10 along. Each of the 11 corner x-planes holds 16 nodes on
    # the inner and on the outer circle plus 8 mid-wall nodes (40); each of the 10 midside
    # x-planes holds 8 on each circle (16). 11 x 40 + 10 x 16 = 600, plus the reference node.
    assert coarse_deck.element_count == len(coarse_frd.elements) == 80
    assert all(len(connectivity) == 20 for connectivity in coarse_frd.elements.values())
    assert len(coarse_frd.nodes) == 600
    assert coarse_deck.node_count == 601


@needs_ccx
def test_tube_closes_on_itself_without_a_seam(coarse_frd):
    rounded = {tuple(round(c, 6) for c in xyz) for xyz in coarse_frd.nodes.values()}
    assert len(rounded) == len(coarse_frd.nodes)


@needs_ccx
def test_midside_nodes_lie_on_the_true_circles(coarse_deck, coarse_frd):
    # Every midspan outer-surface node, corner or midside, is at r_o = 84.15 from the axis (to
    # the .frd print precision); a midside at the chord midpoint would be at 0.92 r_o.
    nodes = coarse_deck.node_sets[MIDSPAN_OUTER_SURFACE]
    assert len(nodes) == 16
    for n in nodes:
        x, y, z = coarse_frd.nodes[n]
        assert x == pytest.approx(500.0)
        assert math.hypot(y, z) == pytest.approx(84.15, rel=1e-5)


@needs_ccx
def test_root_face_is_fixed(coarse_deck, coarse_frd):
    displacements = coarse_frd.nodal_results["DISP"]
    for n in coarse_deck.node_sets[ROOT_FACE]:
        assert coarse_frd.nodes[n][0] == 0.0
        assert displacements[n] == pytest.approx((0.0, 0.0, 0.0), abs=1e-12)


@needs_ccx
def test_tip_face_mean_deflection_matches_the_reference_node(coarse_deck, coarse_job, coarse_frd):
    printed = read_printed_displacements(coarse_job / f"{JOB_NAME}.dat")[REFERENCE_NODE]
    (reference,) = coarse_deck.node_sets[REFERENCE_NODE]
    tip = coarse_deck.node_sets[TIP_FACE]
    assert all(coarse_frd.nodes[n][0] == pytest.approx(1000.0) for n in tip)
    mean_uy = sum(coarse_frd.nodal_results["DISP"][n][1] for n in tip) / len(tip)
    assert mean_uy == pytest.approx(printed[reference][1], rel=1e-4)


@needs_ccx
def test_midspan_top_fibre_is_stretched_and_bottom_fibre_compressed_equally(
    coarse_deck, coarse_frd
):
    (top,) = coarse_deck.node_sets[MIDSPAN_TOP_FIBRE]
    (bottom,) = coarse_deck.node_sets[MIDSPAN_BOTTOM_FIBRE]
    assert coarse_frd.nodes[top] == pytest.approx((500.0, 84.15, 0.0))
    assert coarse_frd.nodes[bottom] == pytest.approx((500.0, -84.15, 0.0))
    stresses = coarse_frd.nodal_results["STRESS"]
    top_sxx, bottom_sxx = stresses[top][0], stresses[bottom][0]
    assert bottom_sxx < 0 < top_sxx
    assert top_sxx == pytest.approx(-bottom_sxx, rel=1e-3)
    # Beam theory: 32.43 MPa (see test_analytical.py); the coarse section is far from converged.
    assert top_sxx == pytest.approx(32.43, rel=0.10)


@pytest.mark.parametrize("divisions", [6, 10, 2])
def test_circumferential_divisions_must_be_a_multiple_of_four(divisions):
    level = MeshLevel("bad", divisions, wall_divisions=1, length_divisions=10)
    with pytest.raises(ValueError, match="multiple of 4"):
        generate_deck(CHS168_CANTILEVER, level)


def test_odd_length_divisions_are_rejected_because_midspan_needs_a_node_plane():
    level = MeshLevel("odd", circumferential_divisions=8, wall_divisions=1, length_divisions=11)
    with pytest.raises(ValueError, match="even"):
        generate_deck(CHS168_CANTILEVER, level)


@needs_ccx
def test_broken_deck_raises_instead_of_returning_results(coarse_deck, tmp_path):
    broken = coarse_deck.text.replace("MATERIAL=STEEL", "MATERIAL=UNDEFINED")
    assert broken != coarse_deck.text
    with pytest.raises(CcxError, match=r"(?s)ccx failed .*ERROR"):
        run_ccx(broken, tmp_path / "broken", CCX)
