"""
Forcing-fragment proof solver for HeXO (VCO: Victory by Continuous Obligations).

The mechanical verifier the 3-SAT programme needs (DIRECTION.md queue item 4,
SPEC.md section 7 item 6): given a position and a bounded zone, prove or refute
"the attacker forces a win within t turns using only forcing moves", where a
forcing pair is one that leaves the obligation family at tau >= 2 -- the
defender's whole 2-stone budget pinned (DIRECTION.md's master variable).

Why this is exact and cheap on the win test:
  - One-turn obligations are 6-windows with >= 4 attacker stones and no
    defender stone; their hyperedge is the window's empty cells, size <= 2.
    So the obligation hypergraph is a *graph*, tau is min vertex cover, and
    tau > 2 is decided by brute-force <=2 hitting-set enumeration -- the same
    object run_tau_lp_gap.py solved by IP/LP and found gap-free (SPEC.md
    Line B table, "tau is LP-exact on real positions").
  - At an attacker-to-move node no obligation can predate the pair (it would
    have been a win-now), so post-pair obligations all contain a just-placed
    stone: obligation rescan is 36 windows, not the whole board.

Soundness contract (stated precisely in
docs/theory/2026-07-19-proof-solver-and-hexanacci.md, revised 2026-07-20
after an external review found the candidate generator was incomplete --
see git history / the note's changelog for exactly what changed):
  - PROVEN is a real forced win in the strong game restricted to the zone:
    defender replies are *completely* enumerated (tau = 2 forces both
    defender stones onto hitting pairs; any non-hitting reply loses at once),
    and defender immediate counter-wins are checked at every AND node. This
    is unaffected by candidate-list truncation -- a cap only removes
    candidates, it cannot fabricate a false win.
  - UNKNOWN is returned instead of a refutation whenever max_pairs truncated
    the candidate list anywhere in the explored tree: a negative result
    reached after a cap fired refutes only the pairs actually tried, not
    the full fragment.
  - REFUTED_FRAGMENT refutes the fully-forcing fragment at this depth, with
    an uncapped candidate generator that is NOT proven complete in general
    (see _forcing_pairs' docstring: complete for pairs where both stones
    are jointly necessary, or one self-sufficient stone paired with a
    single defender counter-threat; a defender with >=2 disjoint win-now
    threats needing >=2 stones to neutralise is a case the generator
    correctly abstains on, which may be a true loss, not a generator gap).
  - REFUTED_CERT: Phi < 1/9 at attacker-to-move refutes *every* attacker
    strategy inside the zone, at any depth (zone-local biased
    Erdos-Selfridge; derivation and proof in the theory note). This is the
    only refutation status with a machine-independent completeness proof.

The 1-2-2 opening asymmetry is deliberately ignored: this is an analysis tool
for positions where both sides have full 2-stone turns (every turn after the
first). Mid-turn mined states are normalised to attacker-to-move-with-2.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import arena  # standalone rules engine (same import pattern as run_tau_lp_gap)

Cell = tuple[int, int]
AXES = ((1, 0), (0, 1), (1, -1))
WIN_LENGTH = 6

# Beck-biased Erdos-Selfridge base for the (2:2) budget: lambda^2 = 1 + q = 3.
# Window of deficit d weighs lambda^(-d) = 3^(-d/2). Thresholds proven in the
# theory note: 1/3 at defender-to-move instants, 1/9 at attacker-to-move
# (one extra factor lambda^2 for the un-answered attacker pair).
CERT_THRESHOLD_OR = 1.0 / 9.0


# -- geometry -----------------------------------------------------------------

def hex_dist(a: Cell, b: Cell) -> int:
    dq, dr = a[0] - b[0], a[1] - b[1]
    return (abs(dq) + abs(dr) + abs(dq + dr)) // 2


def dilate(cells, margin: int) -> set[Cell]:
    """Zone = all cells within hex distance `margin` of the given set.
    The locality lemma (theory note, Lemma 1) says margin = 5 * depth is
    enough to contain every forcing line of that depth."""
    out: set[Cell] = set()
    for (q, r) in cells:
        for dq in range(-margin, margin + 1):
            lo = max(-margin, -dq - margin)
            hi = min(margin, -dq + margin)
            for dr in range(lo, hi + 1):
                out.add((q + dq, r + dr))
    return out


def zone_windows(zone: set[Cell]):
    """Every 6-window lying entirely inside the zone (finite by construction)."""
    for (q, r) in zone:
        for dq, dr in AXES:
            cells = tuple((q + i * dq, r + i * dr) for i in range(WIN_LENGTH))
            if all(c in zone for c in cells):
                yield cells


# -- windows / obligations ------------------------------------------------------

def _windows_through(cell: Cell):
    q, r = cell
    for dq, dr in AXES:
        for offset in range(-(WIN_LENGTH - 1), 1):
            yield tuple((q + (offset + i) * dq, r + (offset + i) * dr)
                        for i in range(WIN_LENGTH))


def _window_state(stones: dict, attacker: int, cells, zone):
    """(own, empties) if window is live for attacker and inside zone, else None."""
    if zone is not None and any(c not in zone for c in cells):
        return None
    defender = arena.other(attacker)
    own, empties = 0, []
    for c in cells:
        occ = stones.get(c)
        if occ == defender:
            return None
        if occ == attacker:
            own += 1
        else:
            empties.append(c)
    return own, empties


def live_windows(stones: dict, attacker: int, zone=None):
    """All live-for-attacker windows touching an attacker stone.
    Yields (cells, own, empties). Deduped by (axis-start)."""
    seen = set()
    for c, p in stones.items():
        if p != attacker:
            continue
        for cells in _windows_through(c):
            if cells in seen:
                continue
            seen.add(cells)
            st = _window_state(stones, attacker, cells, zone)
            if st is not None:
                yield cells, st[0], st[1]


def obligations_all(stones: dict, attacker: int, zone=None) -> list[frozenset]:
    """One-turn obligations (own >= 4, live), dominated supersets dropped.
    Mirrors run_tau_lp_gap.obligation_edges(min_own=4) minus the axis tag."""
    edges = set()
    for _, own, empties in live_windows(stones, attacker, zone):
        if own >= 4 and empties:
            edges.add(frozenset(empties))
    return [e for e in edges if not any(e2 < e for e2 in edges)]


def obligations_through(stones: dict, attacker: int, new_cells, zone=None) -> list[frozenset]:
    """Obligations containing at least one of new_cells. At an OR node with no
    pre-existing win-now window, this is ALL obligations (see module docstring)."""
    edges = set()
    for c in new_cells:
        for cells in _windows_through(c):
            st = _window_state(stones, attacker, cells, zone)
            if st is not None and st[0] >= 4 and st[1]:
                edges.add(frozenset(st[1]))
    return [e for e in edges if not any(e2 < e for e2 in edges)]


def hitting_sets_le2(edges: list[frozenset]):
    """Exact tau capped at 3, plus ALL hitting sets of that size (complete
    defender-reply enumeration when tau = 2: both stones must hit, so both
    lie in the union of edge cells).

    Returns (tau_capped, hitters) with tau_capped in {0,1,2,3}; 3 means > 2.
    """
    if not edges:
        return 0, [frozenset()]
    universe = sorted({v for e in edges for v in e})
    singles = [v for v in universe if all(v in e for e in edges)]
    if singles:
        return 1, [frozenset([v]) for v in singles]
    smallest = min(edges, key=len)
    hitters = set()
    for v in smallest:
        for w in universe:
            if w == v:
                continue
            if all(v in e or w in e for e in edges):
                hitters.add(frozenset((v, w)))
    if hitters:
        return 2, sorted(hitters, key=sorted)
    return 3, []


def exact_tau(edges: list[frozenset]) -> int:
    """Exact minimum hitting-set size, uncapped -- brute force over the
    vertex universe. `hitting_sets_le2` caps at 3 ('>2') for solver speed;
    this is for verification on the small instances the battery uses,
    where the exact value (3 vs 4 vs more) is worth checking, not assuming."""
    if not edges:
        return 0
    universe = sorted({v for e in edges for v in e})
    for k in range(len(universe) + 1):
        for combo in combinations(universe, k):
            s = set(combo)
            if all(s & e for e in edges):
                return k
    return len(universe)


def beck_phi(stones: dict, attacker: int, zone: set[Cell]) -> float:
    """Zone-local biased ES potential: sum over live-for-attacker windows fully
    inside the zone (INCLUDING all-empty ones -- that's what makes it a bound
    on every attacker strategy, and why it must be zone-local: globally the
    all-empty term diverges, the quantitative echo of 'no global pairing/
    potential draw at k=6' (verdicts Theorem 1))."""
    defender = arena.other(attacker)
    phi = 0.0
    for cells in zone_windows(zone):
        own = 0
        dead = False
        for c in cells:
            occ = stones.get(c)
            if occ == defender:
                dead = True
                break
            if occ == attacker:
                own += 1
        if not dead:
            phi += 3.0 ** (-(WIN_LENGTH - own) / 2.0)
    return phi


# -- the solver -----------------------------------------------------------------

@dataclass
class Stats:
    or_nodes: int = 0
    and_nodes: int = 0
    memo_hits: int = 0
    cert_prunes: int = 0
    cap_hits: int = 0          # OR nodes where max_pairs truncated the pair list
    pair_naive: int = 0        # baseline: C(arena.candidates, 2) at each OR node
    pair_generated: int = 0    # pairs actually evaluated
    pair_forcing: int = 0      # pairs that were forcing (tau >= 2 post)
    defender_counterwins: int = 0
    single_forcing_cells: int = 0   # cells that alone push tau >= 2 (spare-paired)


@dataclass
class Result:
    status: str                # proven | refuted_fragment | refuted_cert
    line: list = field(default_factory=list)   # PV when proven
    stats: Stats = field(default_factory=Stats)
    root_phi: float | None = None


def _forcing_pairs(stones, attacker, zone, max_pairs, stats):
    """Candidate attacker pairs.

    Two ways a pair can be forcing:
      1. BOTH new stones are needed jointly: each is an empty of some
         own>=3 window (set P), or both are the two empties of one own==2
         window. (combinations(P,2) and own2_windows below.)
      2. ONE new stone is self-sufficient -- placing it alone already
         pushes tau(O) to >= 2 (e.g. a fork touching >=2 own>=3 windows on
         different axes at once). Attacker stones only ever ADD to
         attacker's own live-window counts, so the second stone of the
         turn cannot lower tau below what the first alone achieves --
         it is free to spend on whatever the position actually needs:
         neutralising the defender's own pre-existing win-now threat(s)
         (defender_threats), or, if there is none, any zone-local spare.
         This is case 2 that the original version omitted entirely (a
         self-forcing cell was only ever paired with OTHER P cells, never
         with a cell outside P) -- confirmed by construction: a 3-axis
         fork at one cell (tau=3 alone) plus a single remote defender
         block was refuted_fragment before this fix, proven after.
    Not claimed complete for case 2 beyond "one threat, one blocker" --
    if the defender has >=2 disjoint own>=4 windows needing >=2 stones to
    neutralise, no single spare resolves it and this generator correctly
    produces no candidate (the position may simply be lost at this depth,
    not a generator gap -- see the theory note's discussion)."""
    P: set[Cell] = set()
    own2_windows = []
    for cells, own, empties in live_windows(stones, attacker, zone):
        if own >= 3:
            P.update(empties)
        elif own == 2:
            own2_windows.append(empties)
    pairs = set()
    for e in own2_windows:
        pairs.update(frozenset(c) for c in combinations(e, 2))
    pairs.update(frozenset(c) for c in combinations(sorted(P), 2))

    defender = arena.other(attacker)
    defender_threats = _defender_threat_empties(stones, defender, zone)
    cand_cells = arena.candidates(stones)
    if zone is not None:
        cand_cells = [c for c in cand_cells if c in zone]
    for c1 in sorted(P):
        trial = dict(stones)
        trial[c1] = attacker
        tau1, _ = hitting_sets_le2(obligations_through(trial, attacker, [c1], zone))
        if tau1 < 2:
            continue
        stats.single_forcing_cells += 1
        partners = set(defender_threats)
        if not partners:
            nearby = sorted((c for c in cand_cells if c != c1),
                            key=lambda c: hex_dist(c, c1))
            partners = set(nearby[:1])
        for c2 in partners:
            if c2 != c1:
                pairs.add(frozenset((c1, c2)))

    pairs = [tuple(sorted(p)) for p in pairs if len(p) == 2]
    # cheap ordering before the cap: prefer pairs that share a window
    # (fork-in-one-line candidates), then tight pairs
    pairs.sort(key=lambda p: (0 if _share_axis_window(p) else 1, hex_dist(*p)))
    stats.pair_generated += min(len(pairs), max_pairs)
    if len(pairs) > max_pairs:
        stats.cap_hits += 1
        pairs = pairs[:max_pairs]
    return pairs


def _share_axis_window(pair) -> bool:
    (q1, r1), (q2, r2) = pair
    dq, dr = q2 - q1, r2 - r1
    for aq, ar in AXES:
        if dq * ar == dr * aq:  # collinear with an axis
            return hex_dist(pair[0], pair[1]) < WIN_LENGTH
    return False


def _defender_can_win_now(stones, defender, zone) -> bool:
    for _, own, empties in live_windows(stones, defender, zone):
        if own >= 4:
            return True
    return False


def _defender_threat_empties(stones, defender, zone) -> set[Cell]:
    """Empties of defender's own pre-existing win-now windows (own >= 4).
    Occupying ANY ONE of a given window's empties kills that window (it
    becomes mixed); this is the candidate set for an attacker's 'spare'
    stone when it must neutralise a remote defender threat rather than
    extend the attacker's own fork."""
    out: set[Cell] = set()
    for _, own, empties in live_windows(stones, defender, zone):
        if own >= 4:
            out.update(empties)
    return out


def _solve_or(stones, attacker, depth, zone, use_cert, max_pairs, stats, memo):
    """Attacker to move with a full 2-stone turn. True iff forced win <= depth."""
    key = (frozenset(stones.items()), depth)
    if key in memo:
        stats.memo_hits += 1
        return memo[key]
    stats.or_nodes += 1

    # 0. win now: any live window with deficit <= 2 completes this turn
    win_now = None
    for cells, own, empties in live_windows(stones, attacker, zone):
        if own >= 4:
            win_now = empties
            break
    if win_now is not None and depth >= 1:
        memo[key] = (True, [("A-win", tuple(win_now))])
        return memo[key]
    if depth <= 1:
        # depth 1 can only cash a win-now; anything deeper needs 2+ turns
        memo[key] = (False, [])
        return memo[key]

    # 0b. hard certificate: Phi < 1/9 at attacker-to-move refutes everything
    if use_cert and zone is not None:
        if beck_phi(stones, attacker, zone) < CERT_THRESHOLD_OR - 1e-12:
            stats.cert_prunes += 1
            memo[key] = (False, [])
            return memo[key]

    n_cands = len(arena.candidates(stones))
    stats.pair_naive += n_cands * (n_cands - 1) // 2

    defender = arena.other(attacker)
    evaluated = []
    for pair in _forcing_pairs(stones, attacker, zone, max_pairs, stats):
        nxt = dict(stones)
        nxt[pair[0]] = attacker
        nxt[pair[1]] = attacker
        edges = obligations_through(nxt, attacker, pair, zone)
        tau, hitters = hitting_sets_le2(edges)
        if tau >= 2:
            stats.pair_forcing += 1
            evaluated.append((tau, pair, nxt, hitters))
    # try tau > 2 (immediate structural win) first, then tau = 2 chains
    evaluated.sort(key=lambda t: -t[0])

    for tau, pair, nxt, hitters in evaluated:
        if tau >= 3:
            # defender cannot cover; attacker completes next turn -- unless the
            # defender wins outright on the reply
            if _defender_can_win_now(nxt, defender, zone):
                stats.defender_counterwins += 1
                continue
            memo[key] = (True, [("A", pair), ("D", "cannot-cover: tau>2")])
            return memo[key]
        # tau == 2: defender pinned onto a hitting pair (AND node)
        stats.and_nodes += 1
        if _defender_can_win_now(nxt, defender, zone):
            stats.defender_counterwins += 1
            continue
        refuted = False
        best_reply_lines = []
        for hit in hitters:
            after = dict(nxt)
            h = tuple(sorted(hit))
            for c in h:
                after[c] = defender
            if any(arena.check_win(after, c[0], c[1], defender) for c in h):
                refuted = True     # blocking stones complete a defender 6
                break
            ok, subline = _solve_or(after, attacker, depth - 1, zone,
                                    use_cert, max_pairs, stats, memo)
            if not ok:
                refuted = True
                break
            best_reply_lines.append((h, subline))
        if not refuted:
            h, subline = best_reply_lines[0]
            memo[key] = (True, [("A", pair), ("D", h)] + subline)
            return memo[key]

    memo[key] = (False, [])
    return memo[key]


def solve(stones: dict, attacker: int, depth: int, zone: set[Cell] | None = None,
          use_cert: bool = True, max_pairs: int = 300) -> Result:
    """Prove/refute a forced fully-forcing win within `depth` attacker turns.

    depth counts attacker turns INCLUDING the final completion turn:
    an open-4 with the move is depth 1; a pair that creates tau > 2 wins at
    depth 2 (pair turn + completion turn).

    PRECONDITION when zone is given: every cell in `stones` must lie inside
    `zone`. Violating this is a real unsoundness, not a style issue --
    windows partially outside zone are invisible to _window_state, so a
    defender stone sitting outside zone can have a genuine, board-real
    win-now threat that the zone-restricted search never sees and never
    checks in _defender_can_win_now, producing a 'proven' verdict that is
    actually false against the real (unrestricted) board. (Found while
    verifying the composition argument in the theory note: a fork position
    with defender material placed outside a too-small zone was reported
    'proven' via a pair that, checked against the real board, left the
    defender free to win on the very next turn.) Zone-restriction is only
    sound as a tool for verifying an ISOLATED position that truly has no
    material beyond the zone -- which is exactly the gadget-composition use
    case, never a shortcut for analysing an arbitrary larger position.
    """
    if zone is not None and any(c not in zone for c in stones):
        raise ValueError(
            "solve(): stones contains cells outside `zone` -- this is unsound "
            "(a defender threat outside zone would be invisible to the search; "
            "see this function's docstring). Either enlarge zone or drop the "
            "out-of-zone stones from the input position.")
    stats = Stats()
    root_phi = None
    if zone is not None:
        root_phi = beck_phi(stones, attacker, zone)
        if use_cert and root_phi < CERT_THRESHOLD_OR - 1e-12:
            return Result("refuted_cert", [], stats, root_phi)
    memo: dict = {}
    ok, line = _solve_or(dict(stones), attacker, depth, zone,
                         use_cert, max_pairs, stats, memo)
    if ok:
        status = "proven"
    elif stats.cap_hits:
        # a negative result is only trustworthy if the candidate generator
        # was never truncated anywhere in the explored tree -- proven
        # results are unaffected (truncation only removes candidates, it
        # can never fabricate a false win), but a refutation reached after
        # a cap fired is not a refutation of the full fragment, just of
        # the pairs actually tried
        status = "unknown"
    else:
        status = "refuted_fragment"
    return Result(status, line, stats, root_phi)
