"""Minimal reader for *NODE PRINT displacement tables in a CalculiX .dat file.

ccx writes only nodes that belong to solid elements to the .frd, so the reference node's
displacement is printed to the .dat instead.
"""

import re
from pathlib import Path

from frd import NodalValues

_HEADER = re.compile(r"displacements \(vx,vy,vz\) for set (\S+) and time")


def read_printed_displacements(path: Path) -> dict[str, NodalValues]:
    """Printed displacements of the last step, keyed by node set name (upper case)."""
    results: dict[str, NodalValues] = {}
    table: NodalValues | None = None
    with path.open() as f:
        for line in f:
            if header := _HEADER.search(line):
                table = {}
                results[header.group(1)] = table
            elif table is not None:
                fields = line.split()
                if not fields:
                    continue
                if not fields[0].isdigit():
                    table = None
                    continue
                table[int(fields[0])] = tuple(float(v) for v in fields[1:])
    return results
