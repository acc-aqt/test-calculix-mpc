import pytest

from benchmark import main
from runner import find_ccx

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
    assert "| κ (Cowper) | 0.5327 |" in text
    assert "| coarse | 80 | 601 |" in text
    assert "1.282" in text  # coarse reference-node tip deflection, mm (+0.076 % vs 1.28126)
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


def test_non_executable_ccx_stops_without_writing_a_report(tmp_path, capsys):
    ccx = tmp_path / "ccx"
    ccx.write_text("#!/bin/sh\necho 'This is Version 2.24'\n")
    ccx.chmod(0o644)

    code, report = run_coarse(tmp_path, ccx)

    assert code == 2
    assert not report.exists()
    assert str(ccx) in capsys.readouterr().err


def test_finished_job_without_result_blocks_stops_without_writing_a_report(tmp_path, capsys):
    ccx = fake_ccx(tmp_path, ": > tube.frd; : > tube.dat; echo ' Job finished'")

    code, report = run_coarse(tmp_path, ccx)

    assert code == 2
    assert not report.exists()
    assert "DISP" in capsys.readouterr().err


def test_finished_job_without_the_reference_node_print_stops_without_writing_a_report(
    tmp_path, capsys
):
    blocks = "printf ' -4  DISP        4    1\\n -3\\n -4  STRESS      6    1\\n -3\\n'"
    ccx = fake_ccx(tmp_path, f"{blocks} > tube.frd; : > tube.dat; echo ' Job finished'")

    code, report = run_coarse(tmp_path, ccx)

    assert code == 2
    assert not report.exists()
    assert "REFNODE" in capsys.readouterr().err


def test_ccx_failure_stops_without_writing_a_report(tmp_path, capsys):
    failing_ccx = tmp_path / "ccx"
    failing_ccx.write_text("#!/bin/sh\necho ' *ERROR in calinput: something broke'\nexit 201\n")
    failing_ccx.chmod(0o755)
    report = tmp_path / "REPORT.md"

    code = main(
        [
            "--levels", "coarse",
            "--report", str(report),
            "--work-dir", str(tmp_path / "work"),
            "--ccx", str(failing_ccx),
        ]
    )  # fmt: skip

    assert code == 2
    assert not report.exists()
    assert "something broke" in capsys.readouterr().err


def test_missing_ccx_stops_without_writing_a_report(tmp_path, capsys):
    report = tmp_path / "REPORT.md"
    code = main(["--report", str(report), "--ccx", str(tmp_path / "no-such-ccx")])

    assert code == 2
    assert not report.exists()
    assert "ccx" in capsys.readouterr().err
