import pytest
from dcoup_variant import distributing_coupling_variant

from benchmark_parameters import COARSE, IPE200_TORSION, MEDIUM, MeshLevel
from dat import read_printed_displacements
from deck import REFERENCE_NODE, generate_deck
from frd import read_frd
from report import TIP_TWIST_TOLERANCE_PERCENT, WARPING_STRESS_TOLERANCE_PERCENT
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
QUARTER_SPAN_WARPING_STRESS = 58.68


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
    # The gap to the thin-walled J grows towards the tip; at midspan it is +2.4 % (prototype).
    midspan = dict(coarse.twist_curve)[IPE200_TORSION.length / 2]
    assert midspan == pytest.approx(0.097760, rel=0.03)


@pytest.fixture(scope="module")
def medium(tmp_path_factory):
    return run_benchmark(MEDIUM, IPE200_TORSION, tmp_path_factory.mktemp("work"), CCX)


def signs(values):
    return tuple(1 if v > 0 else -1 for v in values)


@needs_ccx
@pytest.mark.parametrize("level", ["coarse", "medium"])
def test_flange_tip_warping_stresses_at_quarter_span_show_the_plus_minus_minus_plus_pattern(
    level, request
):
    # Top -z, top +z, bottom -z, bottom +z against E omega phi''(L/4) = 58.68 MPa.
    result = request.getfixturevalue(level)
    assert signs(result.flange_tip_warping_stresses) == (1, -1, -1, 1)
    for value in result.flange_tip_warping_stresses:
        assert abs(value) == pytest.approx(QUARTER_SPAN_WARPING_STRESS, rel=0.05)
    assert all(0 < e <= WARPING_STRESS_TOLERANCE_PERCENT for e in result.warping_stress_errors)


@needs_ccx
def test_medium_warping_stress_errors_settle_within_half_a_point_of_coarse(coarse, medium):
    # Prototype: +3.43 % coarse, +3.84 % medium, +4.10 % fine at every flange tip. The coarse
    # mesh is stiffer in torsion, so as the mesh converges the FE moves away from the thin-walled
    # target towards the solid section's answer (about +4.6 % with the end-corrected J). The
    # medium errors are therefore slightly larger than the coarse ones, not smaller.
    for c, m in zip(coarse.warping_stress_errors, medium.warping_stress_errors, strict=True):
        assert c == pytest.approx(3.43, abs=0.05)
        assert m == pytest.approx(c, abs=0.5)


@needs_ccx
def test_midspan_st_venant_shear_is_reported_for_information(coarse):
    # Prototype: 75.86 MPa at the outstand centres against G t_f phi'(L/2) = 69.10 MPa; the FE
    # twist rate is above Vlasov there, and warping shear is mixed in.
    assert coarse.midspan_st_venant_shear_stress == pytest.approx(75.86, rel=0.01)
    assert coarse.st_venant_shear_stress_error == pytest.approx(9.8, abs=0.2)


@needs_ccx
def test_root_peak_stress_lies_above_the_root_warping_stress(coarse, medium):
    # Information only: the fixed root face is singular where it meets the free surfaces.
    assert coarse.root_peak_von_mises > 148.84
    assert medium.root_peak_von_mises > coarse.root_peak_von_mises


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
