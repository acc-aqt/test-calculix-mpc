import pytest

from benchmark_parameters import COARSE, IPE200_CANTILEVER
from deck import generate_deck
from runner import CcxError, find_ccx, run_benchmark, run_ccx

CCX = find_ccx()

pytestmark = pytest.mark.skipif(
    CCX is None,
    reason="ccx not found: set CCX or run inside the calculix-bench environment",
)


@pytest.fixture(scope="module")
def coarse(tmp_path_factory):
    return run_benchmark(COARSE, IPE200_CANTILEVER, tmp_path_factory.mktemp("work"), CCX)


def test_coarse_reference_node_deflects_down_close_to_timoshenko(coarse):
    # Timoshenko target for the no-fillet IPE 200: 23.57 mm (see test_analytical.py).
    assert coarse.reference_node_uy < 0
    assert -coarse.reference_node_uy == pytest.approx(23.57, rel=0.10)


def test_coarse_reference_node_and_web_centreline_tip_agree(coarse):
    assert coarse.web_centreline_tip_uy == pytest.approx(coarse.reference_node_uy, rel=0.01)


def test_broken_deck_raises_instead_of_returning_results(tmp_path):
    deck = generate_deck(IPE200_CANTILEVER, COARSE).text
    broken = deck.replace("MATERIAL=STEEL", "MATERIAL=UNDEFINED")
    assert broken != deck
    with pytest.raises(CcxError, match=r"(?s)ccx failed .*ERROR"):
        run_ccx(broken, tmp_path / "broken", CCX)
