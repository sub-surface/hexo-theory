import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "hexconnect6_template_atlas.py"
spec = importlib.util.spec_from_file_location("hexconnect6_template_atlas", MODULE_PATH)
atlas = importlib.util.module_from_spec(spec)
spec.loader.exec_module(atlas)


def test_a2_convex_hull_counts_hex_lattice_points():
    corners = {(0, 0), (2, 0), (0, 2)}

    hull = atlas.a2_convex_hull_cells(corners)

    assert hull == {
        (0, 0),
        (1, 0),
        (2, 0),
        (0, 1),
        (1, 1),
        (0, 2),
    }
    assert atlas.a2_convex_deficit(corners) == 3


def test_hex_patch_topology_detects_ring_hole():
    ring = set(atlas.HEX_DIRECTIONS)

    topology = atlas.hex_patch_topology(ring)

    assert topology["hex_components"] == 1
    assert topology["hex_holes"] == 1
    assert topology["hex_euler_characteristic"] == 0
    assert topology["boundary_edge_count"] == 24
    assert topology["manifold_label"] == "annulus"


def test_hex_patch_topology_distinguishes_disconnected_disks():
    cells = {(0, 0), (3, 0)}

    topology = atlas.hex_patch_topology(cells)

    assert topology["hex_components"] == 2
    assert topology["hex_holes"] == 0
    assert topology["hex_euler_characteristic"] == 2
    assert topology["manifold_label"] == "disconnected"


def test_axis_line_arrangement_is_d6_invariant():
    cells = {(0, 0), (1, 0), (1, 1), (3, -1)}
    rotated = {atlas.transform_cell(cell, rot=2, reflect=True) for cell in cells}

    assert atlas.axis_line_arrangement_signature(cells) == atlas.axis_line_arrangement_signature(rotated)
    assert atlas.boundary_slope_partition(cells) == atlas.boundary_slope_partition(rotated)


def test_embedding_manifold_features_are_coordinate_free():
    row = {
        "attacker_stones": "[[0,0],[1,0],[0,1]]",
        "defender_stones": "[]",
        "move_stones": "[[2,0],[0,2]]",
        "obligation_edges": "[[[1,1],[2,1]]]",
    }
    moved = {
        "attacker_stones": "[[10,-4],[11,-4],[10,-3]]",
        "defender_stones": "[]",
        "move_stones": "[[12,-4],[10,-2]]",
        "obligation_edges": "[[[11,-3],[12,-3]]]",
    }

    features = atlas.embedding_manifold_features(row)
    moved_features = atlas.embedding_manifold_features(moved)

    assert features["a2_dimension"] == 2
    assert features["hex_components"] == 1
    assert features["a2_convex_deficit"] == moved_features["a2_convex_deficit"]
    assert features["conway_embedding_signature"] == moved_features["conway_embedding_signature"]
