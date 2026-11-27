import pytest

pytest.importorskip("pyvista")

from benchmark_parameters import COARSE, LE10  # noqa: E402
from deck import generate_deck  # noqa: E402
from frd import read_frd  # noqa: E402
from renders import plate_grid, vtk_hexahedron  # noqa: E402
from runner import find_ccx, run_ccx  # noqa: E402

CCX = find_ccx()


def test_frd_hexahedron_becomes_the_deck_order_vtk_expects():
    # The deck (and VTK) put the midside nodes of the far-face edges at 13-16 and those of the
    # edges joining the faces at 17-20; the .frd swaps them.
    in_frd = tuple(range(1, 13)) + (17, 18, 19, 20, 13, 14, 15, 16)
    in_deck = tuple(range(1, 21))

    assert vtk_hexahedron(in_frd) == in_deck


@pytest.mark.skipif(
    CCX is None, reason="ccx not found: set CCX or run inside the calculix-bench environment"
)
def test_coarse_grid_fills_the_quarter_annulus(tmp_path):
    deck = generate_deck(LE10, COARSE)
    frd = read_frd(run_ccx(deck.text, tmp_path, CCX))

    grid = plate_grid(frd)

    # (π/4)(3250·2750 − 2000·1000) · 600 = 3.2692e9 mm³. VTK measures a quadratic cell by linear
    # pieces through its midside nodes, 12 chords over the quarter ellipse at the coarse level,
    # so it falls short by about (π/24)²/6 = 0.29 %; a wrong node order is far off or negative.
    volumes = grid.compute_cell_sizes(length=False, area=False)["Volume"]
    assert grid.n_cells == 48
    assert volumes.min() > 0
    assert volumes.sum() == pytest.approx(3.2692e9 * (1 - 0.0029), rel=5e-4)
