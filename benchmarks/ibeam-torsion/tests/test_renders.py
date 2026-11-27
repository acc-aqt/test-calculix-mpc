import pytest

pytest.importorskip("pyvista")

from benchmark_parameters import COARSE, IPE200_TORSION  # noqa: E402
from deck import generate_deck  # noqa: E402
from frd import read_frd  # noqa: E402
from renders import beam_grid, vtk_hexahedron  # noqa: E402
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
def test_coarse_grid_fills_the_i_section_times_the_length(tmp_path):
    deck = generate_deck(IPE200_TORSION, COARSE)
    frd = read_frd(run_ccx(deck.text, tmp_path, CCX))

    grid = beam_grid(frd)

    # A = 2 x 100 x 8.5 + 183 x 5.6 = 2724.8 mm^2, times L = 3000 mm.
    volumes = grid.compute_cell_sizes(length=False, area=False)["Volume"]
    assert grid.n_cells == 420
    assert volumes.min() > 0
    assert volumes.sum() == pytest.approx(8_174_400.0, rel=1e-9)
    # The top of the top flange moves towards +z by about h/2 x phi(L) = 100 x 0.276 = 27.6 mm.
    assert grid.point_data["u"][:, 2].max() == pytest.approx(27.6, abs=0.5)
