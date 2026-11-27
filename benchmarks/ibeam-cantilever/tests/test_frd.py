import pytest

from benchmark_parameters import COARSE, IPE200_CANTILEVER
from frd import read_frd
from runner import JOB_NAME, find_ccx, run_benchmark

CCX = find_ccx()

pytestmark = pytest.mark.skipif(
    CCX is None,
    reason="ccx not found: set CCX or run inside the calculix-bench environment",
)


@pytest.fixture(scope="module")
def coarse(tmp_path_factory):
    work_dir = tmp_path_factory.mktemp("work")
    run_benchmark(COARSE, IPE200_CANTILEVER, work_dir, CCX)
    return read_frd(work_dir / COARSE.name / f"{JOB_NAME}.frd")


def test_coarse_has_every_solid_node_but_not_the_reference_node(coarse):
    assert len(coarse.nodes) == 3163


def test_coarse_has_420_twenty_node_elements_on_known_nodes(coarse):
    assert len(coarse.elements) == 420
    assert all(len(connectivity) == 20 for connectivity in coarse.elements.values())
    assert {n for c in coarse.elements.values() for n in c} == set(coarse.nodes)


def test_node_coordinates_span_the_beam(coarse):
    # Root face at x = 0, tip face at x = L = 3000; section 100 wide (z) and 200 deep (y).
    assert coarse.nodes[1] == pytest.approx((0.0, -100.0, -50.0))
    xs, ys, zs = zip(*coarse.nodes.values(), strict=True)
    assert (min(xs), max(xs)) == pytest.approx((0.0, 3000.0))
    assert (min(ys), max(ys)) == pytest.approx((-100.0, 100.0))
    assert (min(zs), max(zs)) == pytest.approx((-50.0, 50.0))


def test_nodal_results_come_with_the_geometry(coarse):
    assert set(coarse.nodal_results["DISP"]) == set(coarse.nodes)
    assert set(coarse.nodal_results["STRESS"]) == set(coarse.nodes)
