import pytest

pytest.importorskip("pyvista")

from benchmark_parameters import CHS168_CANTILEVER, COARSE  # noqa: E402
from frd import read_frd  # noqa: E402
from renders import beam_grid, vtk_hexahedron  # noqa: E402
from runner import JOB_NAME, find_ccx, run_benchmark  # noqa: E402

CCX = find_ccx()


def test_frd_hexahedron_becomes_the_deck_order_vtk_expects():
    # Element 1 of the coarse mesh. The deck (and VTK) put the midside nodes of the far-face
    # edges at 13-16 and those of the edges joining the faces at 17-20; the .frd swaps them.
    in_frd = (1, 57, 81, 25, 3, 59, 83, 27, 41, 73, 49, 17, 2, 58, 82, 26, 42, 74, 50, 18)
    in_deck = (1, 57, 81, 25, 3, 59, 83, 27, 41, 73, 49, 17, 42, 74, 50, 18, 2, 58, 82, 26)

    assert vtk_hexahedron(in_frd) == in_deck


@pytest.mark.skipif(
    CCX is None, reason="ccx not found: set CCX or run inside the calculix-bench environment"
)
def test_coarse_grid_fills_the_annulus_times_the_length(tmp_path):
    run_benchmark(COARSE, CHS168_CANTILEVER, tmp_path, CCX)
    frd = read_frd(tmp_path / COARSE.name / f"{JOB_NAME}.frd")

    grid = beam_grid(frd)

    # A = π (84.15² - 76.15²) = 4028.78 mm², times L = 1000 mm. Straight element edges between
    # the 8 corners would give only 3 627 175 mm³ (-10 %); with the midside nodes on the arcs the
    # quadratic cells, tessellated, come within 0.5 % of the annulus.
    volumes = grid.compute_cell_sizes(length=False, area=False)["Volume"]
    assert grid.n_cells == 80
    assert volumes.min() > 0
    assert grid.tessellate(max_n_subdivide=2).volume == pytest.approx(4_028_778.4, rel=5e-3)
    # The tip drops by about δ_T = 1.281 mm, downwards under the -y load.
    assert grid.point_data["u_y"].min() == pytest.approx(-1.281, abs=0.01)
