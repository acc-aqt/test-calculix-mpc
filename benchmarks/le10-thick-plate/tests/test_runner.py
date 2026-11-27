import pytest
from broken_variants import partial_load_variant, straight_chord_variant

from benchmark_parameters import COARSE, FINE, LE10, MEDIUM
from deck import generate_deck
from frd import read_frd
from reference import quarter_annulus_volume, top_face_area
from runner import (
    CcxError,
    GuardError,
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
def test_coarse_reaction_on_line_ee_balances_the_pressure_on_the_top_face(coarse):
    # Prototype: 5.448647e6 N against 1 MPa x 5 448 699.8 mm^2, -0.001 %.
    assert coarse.reaction_z_on_ee == pytest.approx(5.4486e6, rel=1e-4)
    assert coarse.reaction_z_on_ee == pytest.approx(LE10.pressure * top_face_area(LE10), rel=1e-3)


@needs_ccx
def test_coarse_mesh_volume_matches_the_exact_quarter_annulus_volume(coarse):
    assert coarse.mesh_volume == pytest.approx(quarter_annulus_volume(LE10), rel=1e-3)


@pytest.fixture(scope="module")
def levels(coarse, tmp_path_factory):
    work = tmp_path_factory.mktemp("work")
    return [coarse, *(run_benchmark(level, LE10, work, CCX) for level in (MEDIUM, FINE))]


def surface_traction_components(result):
    """|σ_xx|, |τ_xy|, |τ_yz| and |τ_zx| at D, which vanish in the exact solution."""
    sxx, _, _, sxy, syz, szx = result.stress_at_d
    return tuple(abs(s) for s in (sxx, sxy, syz, szx))


@needs_ccx
def test_sigma_zz_at_d_carries_the_pressure_on_every_level(levels):
    # Prototype: -1.085, -1.053, -1.001 MPa against -p = -1 MPa on the loaded top face.
    for result in levels:
        assert result.stress_at_d[2] == pytest.approx(-LE10.pressure, abs=0.1)


@needs_ccx
def test_traction_free_hole_surface_components_at_d_are_small_and_shrink_with_mesh_level(levels):
    # D is on the traction-free hole surface (normal -x) and the loaded top face, so its exact
    # state is biaxial: sigma_xx and every shear vanish. Prototype largest of them: 0.357,
    # 0.179, 0.059 MPa (sigma_xx) against |sigma_yy| of about 5.4 MPa.
    largest = [max(surface_traction_components(r)) for r in levels]
    for result, value in zip(levels, largest, strict=True):
        assert value < 0.1 * abs(result.stress_yy_at_d)
    assert largest[0] > largest[1] > largest[2]


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


@needs_ccx
def test_pressure_on_part_of_the_top_face_trips_the_reaction_balance_guard(tmp_path):
    deck = generate_deck(LE10, COARSE)
    variant = partial_load_variant(deck)
    assert variant.text != deck.text
    frd = run_ccx(variant.text, tmp_path / "partial", CCX)
    with pytest.raises(GuardError, match="reaction-balance guard"):
        benchmark_result(COARSE, LE10, variant, read_frd(frd), frd.with_suffix(".dat"))


@needs_ccx
def test_straight_chord_midside_nodes_on_the_curved_edges_trip_the_mesh_volume_guard(tmp_path):
    # Straight chords cut the curved edges: the coarse mesh loses about 1 % of its volume.
    deck = generate_deck(LE10, COARSE)
    variant = straight_chord_variant(deck)
    assert variant.text != deck.text
    frd = run_ccx(variant.text, tmp_path / "chord", CCX)
    with pytest.raises(GuardError, match="mesh-volume guard"):
        benchmark_result(COARSE, LE10, variant, read_frd(frd), frd.with_suffix(".dat"))
