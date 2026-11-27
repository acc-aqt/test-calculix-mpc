import subprocess

import pytest

from benchmark_parameters import COARSE, IPE200_TORSION
from deck import BOTTOM_FLANGE_CENTRE_LINE, TOP_FLANGE_CENTRE_LINE, generate_deck
from frd import read_frd
from runner import JOB_NAME, find_ccx, run_ccx

CCX = find_ccx()

pytestmark = pytest.mark.skipif(
    CCX is None,
    reason="ccx not found: set CCX or run inside the calculix-bench environment",
)


@pytest.fixture(scope="module")
def coarse_deck():
    return generate_deck(IPE200_TORSION, COARSE)


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


def test_coarse_mesh_matches_the_ipe200_bending_benchmark(coarse_deck, coarse_frd):
    # Same mapped mesh as the IPE 200 benchmark: 420 C3D20R elements, 3163 solid nodes.
    assert coarse_deck.element_count == len(coarse_frd.elements) == 420
    assert all(len(connectivity) == 20 for connectivity in coarse_frd.elements.values())
    assert len(coarse_frd.nodes) == 3163
    assert coarse_deck.node_count == 3164


def test_flange_centre_lines_lie_on_the_flange_mid_planes_over_the_web(coarse_deck, coarse_frd):
    # h_m / 2 = 95.75 mm; the web footprint is |z| <= t_w / 2 = 2.8 mm.
    for name, y in ((TOP_FLANGE_CENTRE_LINE, 95.75), (BOTTOM_FLANGE_CENTRE_LINE, -95.75)):
        coordinates = [coarse_frd.nodes[n] for n in coarse_deck.node_sets[name]]
        assert all(c[1] == pytest.approx(y) and abs(c[2]) <= 2.8 for c in coordinates)
        assert {c[0] for c in coordinates} >= {0.0, 1500.0, 3000.0}
