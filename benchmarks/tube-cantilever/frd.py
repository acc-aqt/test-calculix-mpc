"""Minimal reader for an ASCII CalculiX .frd file: nodes, elements and nodal result blocks.

The format is fixed-width: a data record is ' -1', a 10-character id, then 12-character values.
Negative values run into their neighbours, so the lines can't be split on whitespace. In the
element block each element's ' -1' record is followed by ' -2' records of 10-character node ids.
"""

from dataclasses import dataclass
from pathlib import Path

NodalValues = dict[int, tuple[float, ...]]

_KEY = slice(0, 3)
_ID = slice(3, 13)
_FIELD_START = 13
_FIELD_WIDTH = 12
_CONNECTIVITY_START = 3
_CONNECTIVITY_WIDTH = 10
_NODE_BLOCK = "    2C"
_ELEMENT_BLOCK = "    3C"


@dataclass(frozen=True)
class FrdResults:
    nodes: dict[int, tuple[float, ...]]
    """Node id to (x, y, z)."""
    elements: dict[int, tuple[int, ...]]
    """Element id to its node ids, in CalculiX order."""
    nodal_results: dict[str, NodalValues]
    """Nodal result blocks of the last step, keyed by block name (e.g. 'DISP', 'STRESS').

    A later step's block replaces an earlier block with the same name.
    """


def read_frd(path: Path) -> FrdResults:
    nodes: NodalValues = {}
    elements: dict[int, list[int]] = {}
    results: dict[str, NodalValues] = {}
    block: NodalValues | None = None
    connectivity: list[int] | None = None
    in_element_block = False
    with path.open() as f:
        for line in f:
            key = line[_KEY]
            if line.startswith(_NODE_BLOCK):
                block = nodes
            elif line.startswith(_ELEMENT_BLOCK):
                in_element_block = True
            elif key == " -4":
                block = {}
                results[line.split()[1]] = block
            elif key == " -1" and in_element_block:
                connectivity = elements.setdefault(int(line[_ID]), [])
            elif key == " -2" and connectivity is not None:
                connectivity.extend(_connectivity(line))
            elif key == " -1" and block is not None:
                block[int(line[_ID])] = _values(line)
            elif key == " -3":
                block = None
                connectivity = None
                in_element_block = False
    return FrdResults(
        nodes=nodes,
        elements={element: tuple(ids) for element, ids in elements.items()},
        nodal_results=results,
    )


def _connectivity(line: str) -> list[int]:
    text = line.rstrip("\n")
    return [
        int(text[start : start + _CONNECTIVITY_WIDTH])
        for start in range(_CONNECTIVITY_START, len(text), _CONNECTIVITY_WIDTH)
    ]


def _values(line: str) -> tuple[float, ...]:
    text = line.rstrip("\n")
    return tuple(
        float(text[start : start + _FIELD_WIDTH])
        for start in range(_FIELD_START, len(text), _FIELD_WIDTH)
    )
