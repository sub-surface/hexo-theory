import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "hexconnect6_template_miner.py"
spec = importlib.util.spec_from_file_location("hexconnect6_template_miner", MODULE_PATH)
miner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(miner)


def test_hitting_number_separates_threat_count_from_exact_pressure():
    many_coverable = [
        ((0, 0), (1, 0)),
        ((0, 0), (2, 0)),
        ((0, 0), (3, 0)),
    ]
    three_independent = [
        ((1, 0),),
        ((0, 1),),
        ((1, -1),),
    ]

    assert miner.hitting_number(many_coverable) == 1
    assert miner.hitting_number(three_independent) == 3


def test_extract_obligations_after_two_stone_move_finds_singletons():
    board = {
        (-4, 0): miner.ATTACKER,
        (-3, 0): miner.ATTACKER,
        (-2, 0): miner.ATTACKER,
        (-1, 0): miner.ATTACKER,
        (0, -4): miner.ATTACKER,
        (0, -3): miner.ATTACKER,
        (0, -2): miner.ATTACKER,
        (0, -1): miner.ATTACKER,
        (-4, 4): miner.ATTACKER,
        (-3, 3): miner.ATTACKER,
        (-2, 2): miner.ATTACKER,
        (-1, 1): miner.ATTACKER,
    }
    move = ((0, 0), (4, -2))
    result = miner.evaluate_move(board, move, miner.ATTACKER, radius=5, include_proto=True)

    assert ((1, 0),) in result.exact_edges
    assert ((0, 1),) in result.exact_edges
    assert ((1, -1),) in result.exact_edges
    assert result.tau_exact >= 3
    assert result.pressure_exact >= 1


def test_canonical_template_signature_is_invariant_under_d6_transform():
    template = miner.Template(
        template_id="raw",
        source_event_id="event",
        kind="exact",
        attacker=((-4, 0), (-3, 0), (-2, 0), (-1, 0)),
        defender=((2, -1),),
        move=((0, 0), (4, -2)),
        obligations=(((1, 0),), ((0, 1),), ((1, -1),)),
        tau=3,
        pressure=1,
        terminal=False,
        source_type="unit",
        pair_shape=miner.canonical_pair_shape(((0, 0), (4, -2))),
    )
    rotated = miner.transform_template(template, rot=2, reflect=True)

    assert miner.canonical_template_signature(template) == miner.canonical_template_signature(rotated)


def test_minimise_template_removes_unrelated_stones_but_keeps_pressure():
    template = miner.Template(
        template_id="raw",
        source_event_id="event",
        kind="exact",
        attacker=(
            (-4, 0),
            (-3, 0),
            (-2, 0),
            (-1, 0),
            (0, -4),
            (0, -3),
            (0, -2),
            (0, -1),
            (-4, 4),
            (-3, 3),
            (-2, 2),
            (-1, 1),
            (5, -4),
        ),
        defender=((-5, 0), (0, -5), (-5, 5), (4, 4)),
        move=((0, 0), (4, -2)),
        obligations=(((1, 0),), ((0, 1),), ((1, -1),)),
        tau=3,
        pressure=1,
        terminal=False,
        source_type="unit",
        pair_shape=miner.canonical_pair_shape(((0, 0), (4, -2))),
    )

    minimized = miner.minimise_template(template, radius=5, mode="same-pressure", max_combo=2)

    assert (5, -4) not in minimized.attacker
    assert (4, 4) not in minimized.defender
    assert minimized.pressure == 1
    assert minimized.tau == 3


def test_minimum_transversal_count_skips_large_combination_spaces():
    edges = tuple(((i, 0), (i, 1)) for i in range(28))

    assert miner.count_minimum_transversals(edges, tau=14, max_combinations=1000) == -1


def test_active_source_types_respects_per_source_positive_cap():
    sources = ["random", "rail", "opening"]
    counts = {"random": 3, "rail": 1, "opening": 0}

    assert miner.active_source_types(sources, counts, cap=3) == ["rail", "opening"]
    assert miner.active_source_types(sources, counts, cap=0) == sources


def test_critical_obligation_core_removes_redundant_edges():
    edges = (
        ((0, 0),),
        ((1, 0),),
        ((2, 0),),
        ((0, 0), (1, 0), (2, 0), (3, 0)),
    )

    core = miner.critical_obligation_core(edges, mode="same-pressure")

    assert core == (((0, 0),), ((1, 0),), ((2, 0),))
    assert miner.hitting_number(core) == 3
