from __future__ import annotations

from .lattices import Cell


def central_seed(q: int) -> set[Cell]:
    """A deterministic q-stone seed near the origin.

    q=1 is the rooted Connect6-style singleton.  q=2 gives a small balanced pair.
    """
    if q <= 0:
        return set()
    base = [(0, 0), (1, 0), (0, 1), (1, -1), (-1, 0), (0, -1)]
    return set(base[:q])


def symmetric_pair_seed() -> set[Cell]:
    return {(-1, 0), (1, 0)}


def named_seed(name: str, q: int = 1) -> set[Cell]:
    if name == "none":
        return set()
    if name == "symmetric-pair":
        return symmetric_pair_seed()
    return central_seed(q)
