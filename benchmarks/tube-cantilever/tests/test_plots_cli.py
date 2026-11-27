import pytest

from benchmark_parameters import CHS168_CANTILEVER, COARSE, MESH_LEVELS
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
    run_benchmark(COARSE, CHS168_CANTILEVER, work_dir, CCX)

    code = main(
        ["--levels", "coarse", "--work-dir", str(work_dir), "--output-dir", str(output_dir)]
    )

    assert code == 0
    pngs = sorted(p.name for p in (output_dir / "figures").glob("*.png"))
    assert [name.split("-")[0] for name in pngs] == [f"fig{n}" for n in range(1, 9)]
    page = (output_dir / "FIGURES.md").read_text()
    assert "Do not edit by hand" in page
    for name in pngs:
        assert f"(figures/{name})" in page


@needs_ccx
def test_levels_given_out_of_order_give_the_same_figures_page_as_the_default(tmp_path):
    work_dir = tmp_path / "work"
    for level in MESH_LEVELS:
        run_benchmark(level, CHS168_CANTILEVER, work_dir, CCX)
    default, reversed_ = tmp_path / "default", tmp_path / "reversed"

    assert main(["--work-dir", str(work_dir), "--output-dir", str(default)]) == 0
    reversed_args = ["--levels", "fine", "medium", "coarse", "fine"]
    assert main([*reversed_args, "--work-dir", str(work_dir), "--output-dir", str(reversed_)]) == 0

    page = (reversed_ / "FIGURES.md").read_text()
    assert page == (default / "FIGURES.md").read_text()
    assert "p = " in page.split("## Figure 8.")[1]


def test_missing_mesh_level_stops_without_writing_anything(tmp_path, capsys):
    output_dir = tmp_path / "out"

    code = main(["--work-dir", str(tmp_path / "work"), "--output-dir", str(output_dir)])

    assert code != 0
    assert "benchmark.py" in capsys.readouterr().err
    assert not output_dir.exists()


def test_one_missing_mesh_level_stops_naming_its_files_and_writes_nothing(tmp_path, capsys):
    work_dir, output_dir = tmp_path / "work", tmp_path / "out"
    for name in ("coarse", "medium"):
        (work_dir / name).mkdir(parents=True)
        for suffix in ("frd", "dat"):
            (work_dir / name / f"tube.{suffix}").write_text("")

    code = main(["--work-dir", str(work_dir), "--output-dir", str(output_dir)])

    assert code != 0
    err = capsys.readouterr().err
    assert str(work_dir / "fine" / "tube.frd") in err
    assert str(work_dir / "fine" / "tube.dat") in err
    assert str(work_dir / "coarse") not in err
    assert str(work_dir / "medium") not in err
    assert not output_dir.exists()
