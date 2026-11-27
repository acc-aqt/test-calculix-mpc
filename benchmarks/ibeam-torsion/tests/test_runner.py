import pytest
from dcoup_variant import distributing_coupling_variant

from benchmark_parameters import COARSE, IPE200_TORSION, MeshLevel
from dat import read_printed_displacements
from deck import REFERENCE_NODE, generate_deck
from frd import read_frd
from report import TIP_TWIST_TOLERANCE_PERCENT
from runner import (
    CcxError,
    ZeroTwistError,
    benchmark_result,
    find_ccx,
    run_benchmark,
    run_ccx,
)

CCX = find_ccx()

needs_ccx = pytest.mark.skipif(
    CCX is None,
    reason="ccx not found: set CCX or run inside the calculix-bench environment",
)

# Targets for the no-fillet IPE 200 under T = 5e5 N mm (see test_analytical.py).
VLASOV_TIP_TWIST = 0.26275
ST_VENANT_TIP_TWIST = 0.35953


@pytest.fixture(scope="module")
def coarse(tmp_path_factory):
    return run_benchmark(COARSE, IPE200_TORSION, tmp_path_factory.mktemp("work"), CCX)


@needs_ccx
def test_coarse_tip_twists_positively_within_the_tolerance_of_vlasov(coarse):
    # Prototype: phi(L) = 0.27599 rad, +5.04 % against Vlasov. The FE beam is softer than the
    # thin-walled J says (see ADR 0003).
    assert coarse.tip_twist > 0
    assert coarse.tip_twist == pytest.approx(
        VLASOV_TIP_TWIST, rel=TIP_TWIST_TOLERANCE_PERCENT / 100
    )
    assert abs(coarse.tip_twist_error) <= TIP_TWIST_TOLERANCE_PERCENT


@needs_ccx
def test_coarse_tip_twist_is_clearly_below_pure_st_venant(coarse):
    assert coarse.tip_twist < 0.8 * ST_VENANT_TIP_TWIST
    assert coarse.st_venant_tip_twist_error == pytest.approx(-23.2, abs=0.2)


@needs_ccx
def test_coarse_twist_curve_runs_from_zero_at_the_root_to_the_tip(coarse):
    xs = [x for x, _ in coarse.twist_curve]
    assert xs[0] == 0.0 and xs[-1] == IPE200_TORSION.length
    assert coarse.twist_curve[0][1] == pytest.approx(0.0, abs=1e-9)
    twists = [phi for _, phi in coarse.twist_curve]
    assert twists == sorted(twists)


@needs_ccx
def test_midspan_twist_is_within_three_percent_of_vlasov(coarse):
    # Away from the tip zone the gap to thin-walled theory is smaller (prototype: +2.4 %).
    midspan = dict(coarse.twist_curve)[IPE200_TORSION.length / 2]
    assert midspan == pytest.approx(0.097760, rel=0.03)


@needs_ccx
def test_distributing_coupling_drops_the_torque_and_trips_the_zero_twist_guard(tmp_path):
    deck = generate_deck(IPE200_TORSION, COARSE)
    variant = distributing_coupling_variant(deck)
    frd = run_ccx(variant.text, tmp_path / "dcoup", CCX)
    with pytest.raises(ZeroTwistError, match="zero-twist guard"):
        benchmark_result(COARSE, IPE200_TORSION, variant, read_frd(frd))


@needs_ccx
def test_reference_node_prints_zero_displacement_under_the_coupling(tmp_path):
    # ADR 0003: ccx reports no motion for the reference node, so twist is measured on the beam.
    deck = generate_deck(IPE200_TORSION, COARSE)
    run_ccx(deck.text, tmp_path, CCX)
    printed = read_printed_displacements(tmp_path / "ibeam.dat")[REFERENCE_NODE]
    assert printed[deck.node_count] == (0.0, 0.0, 0.0)


@pytest.mark.parametrize(
    ("divisions", "message"),
    [((1, 4, 31), "even"), ((0, 4, 30), "flange_thickness_divisions"), ((1, 0, 30), "web")],
)
def test_invalid_divisions_are_rejected(divisions, message):
    with pytest.raises(ValueError, match=message):
        generate_deck(IPE200_TORSION, MeshLevel("bad", *divisions))


@needs_ccx
def test_broken_deck_raises_instead_of_returning_results(tmp_path):
    deck = generate_deck(IPE200_TORSION, COARSE).text
    broken = deck.replace("MATERIAL=STEEL", "MATERIAL=UNDEFINED")
    assert broken != deck
    with pytest.raises(CcxError, match=r"(?s)ccx failed .*ERROR"):
        run_ccx(broken, tmp_path / "broken", CCX)
