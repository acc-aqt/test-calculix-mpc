"""A *DISTRIBUTING COUPLING variant of the torsion deck, the load introduction that drops
the torque (ADR 0003)."""

from dataclasses import replace

from deck import TIP_FACE, TIP_SURFACE, Deck


def distributing_coupling_variant(deck: Deck) -> Deck:
    """The deck with the *COUPLING/*DISTRIBUTING tip replaced by a DCOUP3D element and
    *DISTRIBUTING COUPLING over the tip-face nodes, the moment still on DOF 4 of the
    reference node."""
    text = deck.text
    start = text.index(f"*SURFACE, NAME={TIP_SURFACE}")
    end = text.index("*STEP")
    reference_node = deck.node_count
    dcoup = (
        f"*ELEMENT, TYPE=DCOUP3D, ELSET=ECOUP\n{deck.element_count + 1}, {reference_node}\n"
        f"*DISTRIBUTING COUPLING, ELSET=ECOUP\n{TIP_FACE}, 1.0\n"
    )
    return replace(deck, text=text[:start] + dcoup + text[end:])
