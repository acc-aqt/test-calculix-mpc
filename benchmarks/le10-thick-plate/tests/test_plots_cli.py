import pytest

from benchmark_parameters import COARSE, LE10
from deck import C3D20, C3D20R
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
def test_coarse_work_dir_gives_every_figure_and_the_figures_page(tmp_path):
    work_dir, output_dir = tmp_path / "work", tmp_path / "out"
    for element_type in (C3D20R, C3D20):
        run_benchmark(COARSE, LE10, work_dir, CCX, element_type)

    code = main(
        ["--levels", "coarse", "--work-dir", str(work_dir), "--output-dir", str(output_dir)]
    )

    assert code == 0
    pngs = sorted(p.name for p in (output_dir / "figures").glob("*.png"))
    assert pngs == [
        "fig1-mesh.png",
        "fig2-boundary-conditions.png",
        "fig3-stress-through-thickness.png",
        "fig4-convergence.png",
        "fig5-stress-render.png",
        "fig6-hole-edge-stress.png",
        "fig7-displacement-render.png",
        "fig8-hole-edge-displacement.png",
    ]
    page = (output_dir / "FIGURES.md").read_text()
    assert "Do not edit by hand" in page
    assert "](REPORT.md)" in page
    for number in range(1, 9):
        assert f"## Figure {number}. " in page
    for name in pngs:
        assert f"(figures/{name})" in page


def test_missing_mesh_levels_stop_without_writing_anything(tmp_path, capsys):
    output_dir = tmp_path / "out"

    code = main(["--work-dir", str(tmp_path / "work"), "--output-dir", str(output_dir)])

    assert code != 0
    assert "benchmark.py" in capsys.readouterr().err
    assert not output_dir.exists()


def test_one_missing_result_file_stops_naming_it_and_writes_nothing(tmp_path, capsys):
    work_dir, output_dir = tmp_path / "work", tmp_path / "out"
    for name in ("coarse", "medium", "fine"):
        for element_type in (C3D20R, C3D20):
            (work_dir / name / element_type).mkdir(parents=True)
            (work_dir / name / element_type / "le10.frd").write_text("")
            (work_dir / name / element_type / "le10.dat").write_text("")
    (work_dir / "medium" / "C3D20R" / "le10.dat").unlink()

    code = main(["--work-dir", str(work_dir), "--output-dir", str(output_dir)])

    assert code != 0
    err = capsys.readouterr().err
    assert str(work_dir / "medium" / "C3D20R" / "le10.dat") in err
    assert str(work_dir / "medium" / "C3D20R" / "le10.frd") not in err
    assert str(work_dir / "coarse") not in err
    assert str(work_dir / "fine") not in err
    assert not output_dir.exists()


def test_a_missing_c3d20_level_stops_naming_it_and_writes_nothing(tmp_path, capsys):
    work_dir, output_dir = tmp_path / "work", tmp_path / "out"
    (work_dir / "coarse" / "C3D20R").mkdir(parents=True)
    (work_dir / "coarse" / "C3D20R" / "le10.frd").write_text("")
    (work_dir / "coarse" / "C3D20R" / "le10.dat").write_text("")

    code = main(
        ["--levels", "coarse", "--work-dir", str(work_dir), "--output-dir", str(output_dir)]
    )

    assert code != 0
    err = capsys.readouterr().err
    assert str(work_dir / "coarse" / "C3D20" / "le10.frd") in err
    assert str(work_dir / "coarse" / "C3D20R") not in err
    assert not output_dir.exists()
