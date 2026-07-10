from connectn_lab.d6_seeded_hypergraph import (
    d6_cooccurrence_weight,
    d6_sector,
    hex_spiral,
    run_d6_seeded_process,
)


def test_hex_spiral_has_d6_shell_sizes():
    cells = hex_spiral(radius=2)

    assert cells[0] == ((0, 0), 0)
    assert len(cells) == 19
    assert len({cell for cell, _ in cells}) == 19
    assert [index for _, index in cells[:7]] == list(range(7))


def test_d6_cooccurrence_weight_is_connect6_line_overlap():
    assert d6_cooccurrence_weight((0, 0), (1, 0), k=6) == 5
    assert d6_cooccurrence_weight((0, 0), (5, 0), k=6) == 1
    assert d6_cooccurrence_weight((0, 0), (6, 0), k=6) == 0
    assert d6_cooccurrence_weight((0, 0), (1, 1), k=6) == 0


def test_d6_seeded_process_uses_one_two_two_schedule():
    result = run_d6_seeded_process(radius=4, turns=4, k=6, attack_min_weight=6)

    assert (0, 0) in result.black
    assert len(result.black) == 1 + 2 * 3
    assert len(result.white) == 2 * 4
    assert result.turn_records[0].black_added == tuple()
    assert len(result.turn_records[0].white_added) == 2
    assert len(result.turn_records[1].black_added) == 2


def test_d6_seeded_process_records_obligation_tau_metrics():
    result = run_d6_seeded_process(radius=4, turns=8, k=6, attack_min_weight=1)

    assert result.turn_records
    assert all(record.black_tau >= 0 for record in result.turn_records)
    assert all(record.white_tau >= 0 for record in result.turn_records)
    assert all(0 <= d6_sector(cell) < 6 for cell in result.black | result.white if cell != (0, 0))
