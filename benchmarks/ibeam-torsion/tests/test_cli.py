import os

import pytest
from dcoup_variant import distributing_coupling_variant
from records import result

import benchmark
from benchmark import main
from benchmark_parameters import COARSE, IPE200_TORSION
from deck import generate_deck
from runner import find_ccx, run_ccx

CCX = find_ccx()
needs_ccx = pytest.mark.skipif(
    CCX is None,
    reason="ccx not found: set CCX or run inside the calculix-bench environment",
)


@needs_ccx
def test_coarse_run_writes_a_report_with_version_table_and_no_verdict(tmp_path, capsys):
    report = tmp_path / "REPORT.md"
    code = main(
        ["--levels", "coarse", "--report", str(report), "--work-dir", str(tmp_path / "work")]
    )

    assert code == 0
    text = report.read_text()
    assert "Version 2.24" in text
    assert "| φ(L), Vlasov (target) | 0.26275 rad |" in text
    assert "| coarse | 420 | 3164 | 0.27599 | +5.04 | -23.24 |" in text
    assert "Verdict" in text and "not evaluated" in text
    assert str(report) in capsys.readouterr().out


def fake_ccx(tmp_path, solve):
    """A ccx script that prints a version for -v and runs the shell lines `solve` for -i."""
    ccx = tmp_path / "ccx"
    ccx.write_text(
        f'#!/bin/sh\nif [ "$1" = "-v" ]; then echo "This is Version 2.24"; exit 0; fi\n{solve}\n'
    )
    ccx.chmod(0o755)
    return ccx


def run_coarse(tmp_path, ccx):
    report = tmp_path / "REPORT.md"
    code = main(
        [
            "--levels", "coarse",
            "--report", str(report),
            "--work-dir", str(tmp_path / "work"),
            "--ccx", str(ccx),
        ]
    )  # fmt: skip
    return code, report


def test_failing_fine_level_writes_the_report_and_exits_1(tmp_path, monkeypatch, capsys):
    # A hand-made fine result 20 % off the Vlasov tip twist stands in for the solve.
    monkeypatch.setattr(
        benchmark, "run_benchmark", lambda level, params, work_dir, ccx: result(level, 1.2)
    )
    report = tmp_path / "REPORT.md"
    ccx = fake_ccx(tmp_path, "exit 1")

    code = main(["--levels", "fine", "--report", str(report), "--ccx", str(ccx)])

    assert code == 1
    assert "- Verdict: **FAIL**" in report.read_text()
    assert "Verdict: FAIL" in capsys.readouterr().out


def test_non_executable_ccx_stops_without_writing_a_report(tmp_path, capsys):
    ccx = tmp_path / "ccx"
    ccx.write_text("#!/bin/sh\necho 'This is Version 2.24'\n")
    ccx.chmod(0o644)

    code, report = run_coarse(tmp_path, ccx)

    assert code == 2
    assert not report.exists()
    assert str(ccx) in capsys.readouterr().err


def test_finished_job_without_result_blocks_stops_without_writing_a_report(tmp_path, capsys):
    ccx = fake_ccx(tmp_path, ": > ibeam.frd; : > ibeam.dat; echo ' Job finished'")

    code, report = run_coarse(tmp_path, ccx)

    assert code == 2
    assert not report.exists()
    assert "DISP" in capsys.readouterr().err


@needs_ccx
def test_zero_twist_stops_without_writing_a_report(tmp_path, capsys):
    # A ccx stand-in that hands back the results of the *DISTRIBUTING COUPLING deck variant,
    # which drops the torque: every displacement is zero.
    deck = generate_deck(IPE200_TORSION, COARSE)
    dropped = tmp_path / "dropped"
    run_ccx(distributing_coupling_variant(deck).text, dropped, CCX)
    ccx = fake_ccx(tmp_path, f"cp {dropped / 'ibeam.frd'} ibeam.frd; echo ' Job finished'")

    code, report = run_coarse(tmp_path, ccx)

    assert code == 2
    assert not report.exists()
    assert "zero-twist guard" in capsys.readouterr().err


def test_bare_ccx_name_is_looked_up_on_path(tmp_path, monkeypatch, capsys):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_ccx(bin_dir, "echo ' *ERROR in calinput: found on PATH'; exit 201").rename(
        bin_dir / "my-ccx"
    )
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.chdir(tmp_path)

    code, _ = run_coarse(tmp_path, "my-ccx")

    assert code == 2
    assert "found on PATH" in capsys.readouterr().err


def test_ccx_failure_stops_without_writing_a_report(tmp_path, capsys):
    ccx = fake_ccx(tmp_path, "echo ' *ERROR in calinput: something broke'; exit 201")

    code, report = run_coarse(tmp_path, ccx)

    assert code == 2
    assert not report.exists()
    err = capsys.readouterr().err
    assert "*ERROR in calinput: something broke" in err
    assert "exit code 201" in err


def test_missing_ccx_stops_without_writing_a_report(tmp_path, capsys):
    report = tmp_path / "REPORT.md"
    code = main(["--report", str(report), "--ccx", str(tmp_path / "no-such-ccx")])

    assert code == 2
    assert not report.exists()
    assert "ccx" in capsys.readouterr().err
