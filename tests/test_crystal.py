from engine.crystal import (
    box_count_dimension,
    d6_jaccard,
    harmonic_moments,
    sector_entropy,
)
from engine.isomorphisms import d6_transforms


HEX_RING = ((5, 0), (0, 5), (-5, 5), (-5, 0), (0, -5), (5, -5))


def test_hex_ring_has_large_sixfold_harmonic():
    moments = harmonic_moments(HEX_RING, orders=range(1, 13))

    assert moments[6] > 0.99
    assert moments[1] < 0.01


def test_full_d6_orbit_has_perfect_jaccard_symmetry():
    orbit = set(d6_transforms((3, 1)))

    assert d6_jaccard(orbit) == 1.0


def test_line_has_lower_sector_entropy_than_hex_ring():
    line = tuple((q, 0) for q in range(1, 7))

    assert sector_entropy(line) < sector_entropy(HEX_RING)


def test_box_count_dimension_is_positive_for_nonempty_pattern():
    dim = box_count_dimension(HEX_RING, scales=(1, 2, 4))

    assert dim > 0.0
