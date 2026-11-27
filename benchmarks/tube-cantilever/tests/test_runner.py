import pytest

from benchmark_parameters import CHS168_CANTILEVER, COARSE, MEDIUM, MeshLevel
from deck import MIDSPAN_BOTTOM_FIBRE, MIDSPAN_OUTER_SURFACE, MIDSPAN_TOP_FIBRE, generate_deck
from frd import FrdResults
from runner import CcxError, benchmark_result, find_ccx, run_benchmark, run_ccx

CCX = find_ccx()

needs_ccx = pytest.mark.skipif(
    CCX is None,
    reason="ccx not found: set CCX or run inside the calculix-bench environment",
)


@pytest.fixture(scope="module")
def coarse(tmp_path_factory):
    return run_benchmark(COARSE, CHS168_CANTILEVER, tmp_path_factory.mktemp("work"), CCX)


@pytest.fixture(scope="module")
def medium(tmp_path_factory):
    return run_benchmark(MEDIUM, CHS168_CANTILEVER, tmp_path_factory.mktemp("work"), CCX)


@needs_ccx
def test_coarse_reference_node_deflects_down_within_one_percent_of_timoshenko(coarse):
    # Timoshenko target with Cowper kappa: 1.28126 mm (see test_analytical.py).
    assert coarse.reference_node_uy < 0
    assert -coarse.reference_node_uy == pytest.approx(1.28126, rel=0.01)
    assert coarse.deflection_error == pytest.approx(0, abs=1)


@needs_ccx
def test_coarse_tip_face_mean_deflection_matches_the_reference_node(coarse):
    assert coarse.tip_face_mean_uy == pytest.approx(coarse.reference_node_uy, rel=1e-4)


@needs_ccx
def test_coarse_top_fibre_is_stretched_and_bottom_fibre_compressed_equally(coarse):
    # A tip load in -y hogs the cantilever: tension on top, compression below.
    top, bottom = coarse.top_fibre_sxx, coarse.bottom_fibre_sxx
    assert bottom < 0 < top
    assert top == pytest.approx(-bottom, rel=1e-3)
    # Beam theory: 32.43 MPa (see test_analytical.py); the coarse section is far from converged.
    assert top == pytest.approx(32.43, rel=0.10)
    assert coarse.top_fibre_stress_error == pytest.approx(coarse.bottom_fibre_stress_error)
    assert coarse.top_fibre_stress_error > 0


@needs_ccx
def test_coarse_midspan_stress_fit_is_signed_and_agrees_with_the_single_node_values(coarse):
    top, bottom = coarse.midspan_top_fitted_sxx, coarse.midspan_bottom_fitted_sxx
    assert bottom < 0 < top
    assert top == pytest.approx(-bottom)
    assert top == pytest.approx(coarse.top_fibre_sxx, rel=0.05)
    assert bottom == pytest.approx(coarse.bottom_fibre_sxx, rel=0.05)
    # The fit averages out the single-node error (prototype: +1.35 % fitted, +5.0 % single node).
    assert 0 < coarse.midspan_top_stress_error < coarse.top_fibre_stress_error
    assert coarse.midspan_top_stress_error == pytest.approx(coarse.midspan_bottom_stress_error)
    assert coarse.midspan_top_stress_error == pytest.approx(1.354, abs=0.01)


@needs_ccx
def test_coarse_root_peak_von_mises_is_at_least_the_beam_theory_root_bending_stress(coarse):
    # P L r_o / I = 10000 x 1000 x 84.15 / 1.2973e7 = 64.87 MPa; the fixed end adds to it.
    assert coarse.root_peak_von_mises >= 64.87


@needs_ccx
def test_medium_stress_errors_are_smaller_than_coarse_at_both_fibres(coarse, medium):
    assert abs(medium.midspan_top_stress_error) < abs(coarse.midspan_top_stress_error)
    assert abs(medium.midspan_bottom_stress_error) < abs(coarse.midspan_bottom_stress_error)
    assert abs(medium.top_fibre_stress_error) < abs(coarse.top_fibre_stress_error)
    assert abs(medium.bottom_fibre_stress_error) < abs(coarse.bottom_fibre_stress_error)


@needs_ccx
def test_medium_deflection_matches_cowper_better_than_thin_wall_or_euler_bernoulli(medium):
    # Prototype: -0.009 % vs Cowper, -0.30 % vs kappa = 0.5, +4.7 % vs Euler-Bernoulli.
    assert medium.deflection_error == pytest.approx(0, abs=0.05)
    assert medium.thin_wall_deflection_error == pytest.approx(-0.30, abs=0.05)
    assert medium.euler_bernoulli_deflection_error == pytest.approx(4.71, abs=0.05)


def test_midspan_stress_fit_measures_each_fibre_from_a_line_with_an_intercept(tmp_path):
    # Synthetic midspan stresses sxx = 0.4 y - 2 MPa: the top fibre (y = r_o = 84.15 mm) is at
    # +31.66 MPa and the bottom fibre at -35.66 MPa, so the two fibres differ in magnitude.
    deck = generate_deck(CHS168_CANTILEVER, COARSE)
    r_o = CHS168_CANTILEVER.section.outer_radius
    (top,) = deck.node_sets[MIDSPAN_TOP_FIBRE]
    (bottom,) = deck.node_sets[MIDSPAN_BOTTOM_FIBRE]
    others = [n for n in deck.node_sets[MIDSPAN_OUTER_SURFACE] if n not in (top, bottom)]
    ys = {n: r_o * (2 * i / len(others) - 1) for i, n in enumerate(others)}
    ys |= {top: r_o, bottom: -r_o}
    node_ids = range(1, deck.node_count + 1)
    frd = FrdResults(
        nodes={n: (0.0, ys.get(n, 0.0), 0.0) for n in node_ids},
        elements={},
        nodal_results={
            "DISP": {n: (0.0, -1.0, 0.0) for n in node_ids},
            "STRESS": {n: (0.4 * ys.get(n, 0.0) - 2.0, 0, 0, 0, 0, 0) for n in node_ids},
        },
    )
    dat = tmp_path / "tube.dat"
    dat.write_text(
        " displacements (vx,vy,vz) for set REFNODE and time  0.1000000E+01\n\n"
        f"{deck.node_count:>10}  0.000000E+00 -1.000000E+00  0.000000E+00\n"
    )

    result = benchmark_result(COARSE, CHS168_CANTILEVER, deck, frd, dat)

    assert result.midspan_top_fitted_sxx == pytest.approx(31.66)
    assert result.midspan_bottom_fitted_sxx == pytest.approx(-35.66)


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
def test_broken_deck_raises_instead_of_returning_results(tmp_path):
    deck = generate_deck(CHS168_CANTILEVER, COARSE).text
    broken = deck.replace("MATERIAL=STEEL", "MATERIAL=UNDEFINED")
    assert broken != deck
    with pytest.raises(CcxError, match=r"(?s)ccx failed .*ERROR"):
        run_ccx(broken, tmp_path / "broken", CCX)
