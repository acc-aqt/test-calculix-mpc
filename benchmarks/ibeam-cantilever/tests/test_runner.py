import pytest

from benchmark_parameters import COARSE, IPE200_CANTILEVER, MEDIUM
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


@pytest.fixture(scope="module")
def medium(tmp_path_factory):
    return run_benchmark(MEDIUM, IPE200_CANTILEVER, tmp_path_factory.mktemp("work"), CCX)


def test_medium_mesh_is_closer_to_timoshenko_than_coarse_and_within_five_percent(coarse, medium):
    assert abs(medium.deflection_error) < abs(coarse.deflection_error)
    assert medium.deflection_error == pytest.approx(0, abs=5)
    assert medium.midspan_top_stress_error == pytest.approx(0, abs=5)
    assert medium.midspan_bottom_stress_error == pytest.approx(0, abs=5)


def test_coarse_reference_node_deflects_down_close_to_timoshenko(coarse):
    # Timoshenko target for the no-fillet IPE 200: 23.57 mm (see test_analytical.py).
    assert coarse.reference_node_uy < 0
    assert -coarse.reference_node_uy == pytest.approx(23.57, rel=0.10)


def test_coarse_reference_node_and_web_centreline_tip_agree(coarse):
    assert coarse.web_centreline_tip_uy == pytest.approx(coarse.reference_node_uy, rel=0.01)


def test_coarse_midspan_top_flange_is_stretched_and_bottom_flange_compressed_equally(coarse):
    # A tip load in -y gives a hogging moment along a cantilever: tension on top, compression
    # below. (Spec #1 and ticket #6 state the opposite signs; that is a sign slip in the spec.)
    top, bottom = coarse.midspan_top_sxx_width_mean, coarse.midspan_bottom_sxx_width_mean
    assert bottom < 0 < top
    assert top == pytest.approx(-bottom, rel=0.05)


def test_coarse_midspan_stress_errors_are_within_ten_percent_of_beam_theory(coarse):
    # P (L/2) c / I = 10000 x 1500 x 100 / 18455902.2 = 81.27 MPa; errors are on magnitudes.
    assert coarse.midspan_top_stress_error == pytest.approx(0, abs=10)
    assert coarse.midspan_bottom_stress_error == pytest.approx(0, abs=10)
    assert coarse.midspan_top_sxx_width_mean == pytest.approx(81.27, rel=0.10)


def test_coarse_root_peak_von_mises_is_at_least_the_beam_theory_root_bending_stress(coarse):
    # P L c / I = 10000 x 3000 x 100 / 18455902.2 = 162.55 MPa; the fixed end adds to it.
    assert coarse.root_peak_von_mises >= 162.55


def test_broken_deck_raises_instead_of_returning_results(tmp_path):
    deck = generate_deck(IPE200_CANTILEVER, COARSE).text
    broken = deck.replace("MATERIAL=STEEL", "MATERIAL=UNDEFINED")
    assert broken != deck
    with pytest.raises(CcxError, match=r"(?s)ccx failed .*ERROR"):
        run_ccx(broken, tmp_path / "broken", CCX)
