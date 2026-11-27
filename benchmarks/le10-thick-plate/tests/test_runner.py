import numpy as np
import pytest

from benchmark_parameters import COARSE, LE10
from deck import generate_deck
from runner import CcxError, find_ccx, run_benchmark, run_ccx

CCX = find_ccx()

needs_ccx = pytest.mark.skipif(
    CCX is None,
    reason="ccx not found: set CCX or run inside the calculix-bench environment",
)


@pytest.fixture(scope="module")
def coarse(tmp_path_factory):
    return run_benchmark(COARSE, LE10, tmp_path_factory.mktemp("work"), CCX)


@needs_ccx
def test_coarse_sigma_yy_at_d_is_compressive_and_of_the_published_order(coarse):
    # Prototype: -5.424 MPa, +0.8 % against -5.38 MPa.
    assert coarse.stress_yy_at_d < 0
    assert coarse.stress_yy_at_d == pytest.approx(-5.38, rel=0.25)
    assert coarse.stress_yy_at_d_error == pytest.approx(0.82, abs=0.01)


@needs_ccx
def test_coarse_state_at_d_is_triaxial(coarse):
    # D lies on the y = 0 symmetry plane and on the top face, so the shear components vanish
    # there and the normal components are the principal stresses. All three are compressive,
    # and the smallest (sigma_xx, prototype -0.36 MPa) is not negligible against sigma_yy.
    sxx, syy, szz, *_ = coarse.stress_at_d
    principal = np.linalg.eigvalsh(tensor(coarse.stress_at_d))
    assert all(principal < 0)
    assert min(abs(principal)) > 0.05 * max(abs(principal))
    assert szz == pytest.approx(-LE10.pressure, rel=0.15)
    assert syy == pytest.approx(min(principal), rel=0.01)


@needs_ccx
def test_coarse_von_mises_at_d_follows_from_the_tensor(coarse):
    # The normal components alone give about 4.7 MPa (prototype).
    assert coarse.von_mises_at_d == pytest.approx(4.7, rel=0.05)


@needs_ccx
def test_nearest_integration_point_lies_inside_the_corner_element_and_is_less_compressive(
    coarse,
):
    # Prototype: -3.82 MPa at (2062.8, 60.6, 236.6) mm; ccx extrapolates from there to D.
    x, y, z = coarse.integration_point_at_d
    assert 2000 < x < 2300 and 0 < y < 300 and 150 < z < 300
    assert coarse.stress_yy_at_d < coarse.integration_point_stress_yy_at_d < 0


@needs_ccx
def test_broken_deck_raises_instead_of_returning_results(tmp_path):
    deck = generate_deck(LE10, COARSE).text
    broken = deck.replace("MATERIAL=STEEL", "MATERIAL=UNDEFINED")
    assert broken != deck
    with pytest.raises(CcxError, match=r"(?s)ccx failed .*ERROR"):
        run_ccx(broken, tmp_path / "broken", CCX)


def tensor(stress):
    """The 3 x 3 tensor of a .frd STRESS record (sxx, syy, szz, sxy, syz, szx)."""
    sxx, syy, szz, sxy, syz, szx = stress
    return np.array([[sxx, sxy, szx], [sxy, syy, syz], [szx, syz, szz]])
