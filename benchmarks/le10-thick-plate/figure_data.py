"""What the figures draw from one solved mesh level. No rendering."""

from dataclasses import dataclass

from deck import Deck
from frd import FrdResults
from runner import BenchmarkResult


@dataclass(frozen=True)
class MeshLevelResults:
    result: BenchmarkResult
    deck: Deck
    frd: FrdResults
