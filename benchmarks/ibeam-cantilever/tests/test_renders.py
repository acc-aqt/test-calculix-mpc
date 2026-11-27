import pytest

pytest.importorskip("pyvista")

from benchmark_parameters import COARSE, IPE200_CANTILEVER  # noqa: E402
from frd import read_frd  # noqa: E402
from renders import beam_grid, vtk_hexahedron  # noqa: E402
from runner import JOB_NAME, find_ccx, run_benchmark  # noqa: E402

CCX = find_ccx()


def test_frd_hexahedron_becomes_the_deck_order_vtk_expects():
    # Element 1 of the coarse mesh. The deck (and VTK) put the midside nodes of the far-face
    # edges at 13-16 and those of the edges joining the faces at 17-20; the .frd swaps them.
    in_frd = (1, 104, 121, 18, 3, 106, 123, 20, 74, 115, 80, 12, 2, 105, 122, 19, 75, 116, 81, 13)
    in_deck = (1, 104, 121, 18, 3, 106, 123, 20, 74, 115, 80, 12, 75, 116, 81, 13, 2, 105, 122, 19)

    assert vtk_hexahedron(in_frd) == in_deck


@pytest.mark.skipif(
    CCX is None, reason="ccx not found: set CCX or run inside the calculix-bench environment"
)
def test_coarse_grid_fills_the_section_times_the_length(tmp_path):
    run_benchmark(COARSE, IPE200_CANTILEVER, tmp_path, CCX)
    frd = read_frd(tmp_path / COARSE.name / f"{JOB_NAME}.frd")

    grid = beam_grid(frd)

    # A = 2 x 100 x 8.5 + (200 - 2 x 8.5) x 5.6 = 2724.8 mm², times L = 3000 mm.
    volumes = grid.compute_cell_sizes(length=False, area=False)["Volume"]
    assert grid.n_cells == 420
    assert volumes.min() > 0
    assert volumes.sum() == pytest.approx(8_174_400.0)
    # The tip drops by about δ_T = 23.57 mm, downwards under the -y load.
    assert grid.point_data["u_y"].min() == pytest.approx(-23.57, abs=0.1)
