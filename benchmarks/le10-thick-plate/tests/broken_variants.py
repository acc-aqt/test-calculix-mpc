"""Quietly wrong variants of the LE10 deck, each one meant to trip one sanity guard."""

from dataclasses import replace

from deck import C3D20_OFFSETS, TOP_FACE_LABEL, Deck

_NODE_BLOCK_START = "*NODE, NSET=NALL\n"
_NODE_BLOCK_END = "*ELEMENT"


def straight_chord_variant(deck: Deck) -> Deck:
    """The deck with every midside node at the midpoint of its edge's corners, so the curved
    edges become straight chords. Radial and through-thickness edges are straight already."""
    nodes = dict(deck.nodes)
    corners = C3D20_OFFSETS[:8]
    for element in deck.elements:
        for local, offset in enumerate(C3D20_OFFSETS[8:], start=8):
            ends = [element[c] for c, corner in enumerate(corners) if _is_edge_end(corner, offset)]
            start, end = (deck.nodes[n] for n in ends)
            nodes[element[local]] = tuple((p + q) / 2 for p, q in zip(start, end, strict=True))
    node_lines = "".join(f"{nid}, {x!r}, {y!r}, {z!r}\n" for nid, (x, y, z) in nodes.items())
    head, rest = deck.text.split(_NODE_BLOCK_START)
    tail = rest[rest.index(_NODE_BLOCK_END) :]
    return replace(deck, text=head + _NODE_BLOCK_START + node_lines + tail, nodes=nodes)


def _is_edge_end(corner: tuple[int, int, int], midside: tuple[int, int, int]) -> bool:
    return sum(abs(c - m) for c, m in zip(corner, midside, strict=True)) == 1


def partial_load_variant(deck: Deck) -> Deck:
    """The deck with the top-face pressure surface cut to its first half of elements, so only
    part of the top face is loaded."""
    lines = deck.text.splitlines()
    face_lines = [line for line in lines if line.endswith(f", {TOP_FACE_LABEL}")]
    dropped = set(face_lines[len(face_lines) // 2 :])
    text = "\n".join(line for line in lines if line not in dropped) + "\n"
    return replace(deck, text=text)
