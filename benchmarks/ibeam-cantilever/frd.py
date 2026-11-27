"""Minimal reader for nodal result blocks in an ASCII CalculiX .frd file.

The format is fixed-width: a data record is ' -1', a 10-character node id, then 12-character
values. Negative values run into their neighbours, so the lines can't be split on whitespace.
"""

from pathlib import Path

NodalValues = dict[int, tuple[float, ...]]

_KEY = slice(0, 3)
_NODE = slice(3, 13)
_FIELD_START = 13
_FIELD_WIDTH = 12


def read_nodal_results(path: Path) -> dict[str, NodalValues]:
    """Nodal result blocks of the last step, keyed by block name (e.g. 'DISP', 'STRESS').

    A later step's block replaces an earlier block with the same name.
    """
    results: dict[str, NodalValues] = {}
    block: NodalValues | None = None
    with path.open() as f:
        for line in f:
            key = line[_KEY]
            if key == " -4":
                block = {}
                results[line.split()[1]] = block
            elif key == " -1" and block is not None:
                block[int(line[_NODE])] = _values(line)
            elif key == " -3":
                block = None
    return results


def _values(line: str) -> tuple[float, ...]:
    text = line.rstrip("\n")
    return tuple(
        float(text[start : start + _FIELD_WIDTH])
        for start in range(_FIELD_START, len(text), _FIELD_WIDTH)
    )
