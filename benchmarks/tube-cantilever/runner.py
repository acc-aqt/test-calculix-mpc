"""Running ccx: find the executable, read its version and solve a deck."""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

JOB_NAME = "tube"


class CcxError(RuntimeError):
    """ccx did not finish the job, so there are no results to trust."""


def find_ccx() -> Path | None:
    """The ccx executable: $CCX if set, else ccx on PATH, else the running Python env's ccx.

    None when the chosen candidate doesn't exist.
    """
    if override := os.environ.get("CCX"):
        candidate = Path(override)
    elif on_path := shutil.which("ccx"):
        candidate = Path(on_path)
    else:
        candidate = Path(sys.prefix) / "bin" / "ccx"
    return candidate if candidate.is_file() else None


def ccx_version(ccx: Path) -> str:
    """The version line printed by `ccx -v`, e.g. "Version 2.24". ccx exits 201 here, so the
    exit code is ignored."""
    completed = subprocess.run([str(ccx), "-v"], capture_output=True, text=True, check=False)
    match = re.search(r"Version \S+", completed.stdout)
    if match is None:
        raise CcxError(f"could not read the ccx version from `{ccx} -v`:\n{completed.stdout}")
    return match.group(0)


def run_ccx(deck_text: str, job_dir: Path, ccx: Path) -> Path:
    """Write the deck into job_dir, solve it and return the .frd path. Raises CcxError."""
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / f"{JOB_NAME}.inp").write_text(deck_text)
    completed = subprocess.run(
        [str(ccx), "-i", JOB_NAME], cwd=job_dir, capture_output=True, text=True, check=False
    )
    output = completed.stdout + completed.stderr
    frd = job_dir / f"{JOB_NAME}.frd"
    if completed.returncode != 0 or "Job finished" not in output or not frd.is_file():
        errors = [line for line in output.splitlines() if "ERROR" in line]
        detail = "\n".join(errors) or "\n".join(output.splitlines()[-20:])
        raise CcxError(f"ccx failed in {job_dir} (exit code {completed.returncode}):\n{detail}")
    return frd
