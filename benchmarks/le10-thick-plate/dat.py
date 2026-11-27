"""Minimal reader for *NODE PRINT displacement and reaction-total tables and *EL PRINT
integration-point tables in a CalculiX .dat file.

ccx writes nodal values, extrapolated from the integration points, to the .frd; the
integration-point values themselves are only printed to the .dat.
"""

import re
from pathlib import Path

from frd import NodalValues

_HEADER = re.compile(r"displacements \(vx,vy,vz\) for set (\S+) and time")
_TOTAL_FORCE_HEADER = re.compile(r"total force \(fx,fy,fz\) for set (\S+) and time")
_ELEMENT_HEADER = re.compile(r"^ (stresses|global coordinates) \(elem, integ\.pnt\.,")

IntegrationPointValues = dict[tuple[int, int], tuple[float, ...]]
"""(element, integration point) to the printed values."""


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


def read_printed_integration_points(path: Path) -> dict[str, IntegrationPointValues]:
    """Printed integration-point tables of the last step, keyed by "stresses" and "global
    coordinates". Stresses are in .dat order (sxx, syy, szz, sxy, sxz, syz)."""
    results: dict[str, IntegrationPointValues] = {}
    table: IntegrationPointValues | None = None
    with path.open() as f:
        for line in f:
            if header := _ELEMENT_HEADER.search(line):
                table = {}
                results[header.group(1)] = table
            elif table is not None:
                fields = line.split()
                if not fields:
                    continue
                if not fields[0].isdigit():
                    table = None
                    continue
                key = (int(fields[0]), int(fields[1]))
                table[key] = tuple(float(v) for v in fields[2:])
    return results


def read_printed_total_forces(path: Path) -> dict[str, tuple[float, float, float]]:
    """Printed *NODE PRINT, TOTALS=ONLY reaction totals (fx, fy, fz) of the last step, keyed by
    node set name (upper case)."""
    results: dict[str, tuple[float, float, float]] = {}
    name: str | None = None
    with path.open() as f:
        for line in f:
            if header := _TOTAL_FORCE_HEADER.search(line):
                name = header.group(1)
            elif name is not None and line.strip():
                fx, fy, fz = (float(v) for v in line.split())
                results[name] = (fx, fy, fz)
                name = None
    return results
