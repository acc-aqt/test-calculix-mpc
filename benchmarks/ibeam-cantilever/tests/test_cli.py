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
    assert "18455902" in text.replace(",", "").replace(" ", "")  # I in mm^4
    assert "| coarse | 420 | 3164 |" in text
    assert "23.56" in text  # coarse reference-node tip deflection, mm
    assert "Verdict" in text and "not evaluated" in text
    assert str(report) in capsys.readouterr().out


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

    assert code != 0
    assert not report.exists()
    assert "something broke" in capsys.readouterr().err


def test_missing_ccx_stops_without_writing_a_report(tmp_path, capsys):
    report = tmp_path / "REPORT.md"
    code = main(["--report", str(report), "--ccx", str(tmp_path / "no-such-ccx")])

    assert code != 0
    assert not report.exists()
    assert "ccx" in capsys.readouterr().err
