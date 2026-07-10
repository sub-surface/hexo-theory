from connectn_lab.connect_k_parity import (
    black_first_reply_envelope,
    first_threat_tempo_owner,
    is_prime,
    seed_obligation_stats,
    sweep_connect_k,
    white_opening_obligation_stats,
)


def test_prime_and_first_tempo_classification():
    assert not is_prime(1)
    assert is_prime(2)
    assert is_prime(3)
    assert is_prime(5)
    assert not is_prime(6)

    assert first_threat_tempo_owner(3) == "black"
    assert first_threat_tempo_owner(4) == "white"
    assert first_threat_tempo_owner(5) == "black"
    assert first_threat_tempo_owner(6) == "white"


def test_seed_obligation_stats_detect_connect3_collapse():
    k3 = seed_obligation_stats(k=3, radius=3)
    k4 = seed_obligation_stats(k=4, radius=3)

    assert k3.obligations > 0
    assert k3.tau > 2
    assert k4.obligations == 0
    assert k4.tau == 0


def test_white_opening_stats_show_connect4_even_tempo():
    stats = white_opening_obligation_stats(k=4, radius=3, opening_limit=12)

    assert stats.openings == 12
    assert stats.urgent_openings > 0
    assert stats.max_tau >= 1


def test_black_first_reply_envelope_separates_k4_and_k6():
    k4 = black_first_reply_envelope(k=4, radius=3, opening_limit=12)
    k6 = black_first_reply_envelope(k=6, radius=3, opening_limit=12)

    assert k4.safe_replies_with_tau_gt2 > 0
    assert k4.max_black_tau_after_safe_reply > 2
    assert k6.max_black_tau_after_safe_reply == 0


def test_sweep_connect_k_returns_prime_and_composite_rows():
    rows = sweep_connect_k(k_min=3, k_max=6, opening_limit=8)

    assert [row.k for row in rows] == [3, 4, 5, 6]
    assert rows[0].prime is True
    assert rows[1].prime is False
    assert rows[2].tempo_owner == "black"
    assert rows[3].tempo_owner == "white"
