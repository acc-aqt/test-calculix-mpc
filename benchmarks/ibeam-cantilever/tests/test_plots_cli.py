import pytest

from benchmark_parameters import COARSE, IPE200_CANTILEVER
from runner import find_ccx, run_benchmark

pytest.importorskip("matplotlib")
pytest.importorskip("pyvista")

from plots import main  # noqa: E402

CCX = find_ccx()
needs_ccx = pytest.mark.skipif(
    CCX is None,
    reason="ccx not found: set CCX or run inside the calculix-bench environment",
)


@needs_ccx
def test_coarse_work_dir_gives_the_figures_and_the_figures_page(tmp_path):
    work_dir, output_dir = tmp_path / "work", tmp_path / "out"
    run_benchmark(COARSE, IPE200_CANTILEVER, work_dir, CCX)

    code = main(
        ["--levels", "coarse", "--work-dir", str(work_dir), "--output-dir", str(output_dir)]
    )

    assert code == 0
    pngs = sorted(p.name for p in (output_dir / "figures").glob("*.png"))
    assert [name[:5] for name in pngs] == ["fig5-", "fig6-", "fig7-", "fig8-"]
    page = (output_dir / "FIGURES.md").read_text()
    assert "Do not edit by hand" in page
    for name in pngs:
        assert f"(figures/{name})" in page


def test_missing_mesh_level_stops_without_writing_anything(tmp_path, capsys):
    output_dir = tmp_path / "out"

    code = main(["--work-dir", str(tmp_path / "work"), "--output-dir", str(output_dir)])

    assert code != 0
    assert "benchmark.py" in capsys.readouterr().err
    assert not output_dir.exists()
