"""Toy algebra for HeXO's two-placement local-game sums."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Component:
    """A local hot component with move scores in descending order."""

    name: str
    moves: tuple[float, ...]


@dataclass(frozen=True)
class Choice:
    """The best component allocation and its additive toy score."""

    components: tuple[str, ...]
    score: float


def best_one_move_sum(components: tuple[Component, ...]) -> Choice:
    """Best ordinary disjunctive-sum move: spend one move in one component."""
    options = [
        Choice((component.name,), float(component.moves[0]))
        for component in components
        if component.moves
    ]
    if not options:
        return Choice((), 0.0)
    return max(options, key=lambda option: option.score)


def best_two_move_sum(components: tuple[Component, ...]) -> Choice:
    """
    Best two-placement allocation across local components.

    This is deliberately a small empirical model, not a full CGT value system:
    it tests the HeXO-specific distinction between spending both placements in
    one component and splitting them across two components.
    """
    options: list[Choice] = []
    for i, first in enumerate(components):
        if not first.moves:
            continue
        for j, second in enumerate(components):
            if i == j:
                if len(first.moves) >= 2:
                    options.append(
                        Choice(
                            (first.name, first.name),
                            float(first.moves[0] + first.moves[1]),
                        )
                    )
            elif second.moves:
                options.append(
                    Choice(
                        tuple(sorted((first.name, second.name))),
                        float(first.moves[0] + second.moves[0]),
                    )
                )
    if not options:
        return Choice((), 0.0)
    return max(options, key=lambda option: option.score)
