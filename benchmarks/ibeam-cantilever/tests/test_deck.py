import pytest

from benchmark_parameters import IPE200_CANTILEVER, MeshLevel
from deck import MIDSPAN_BOTTOM_FLANGE, MIDSPAN_TOP_FLANGE, generate_deck


@pytest.mark.parametrize("length_divisions", [30, 60, 120])
def test_midspan_flange_sets_span_the_flange_width_for_even_length_divisions(length_divisions):
    # Flange width 100 = two outstands of 2 elements plus 1 web element: 5 elements, 11 nodes.
    deck = generate_deck(IPE200_CANTILEVER, MeshLevel("even", 1, 4, length_divisions))
    assert len(deck.node_sets[MIDSPAN_TOP_FLANGE]) == 11
    assert len(deck.node_sets[MIDSPAN_BOTTOM_FLANGE]) == 11
    assert f"*NSET, NSET={MIDSPAN_TOP_FLANGE}" in deck.text


def test_odd_length_divisions_are_rejected_because_midspan_needs_a_node_plane():
    with pytest.raises(ValueError, match="even"):
        generate_deck(IPE200_CANTILEVER, MeshLevel("odd", 1, 4, 31))
