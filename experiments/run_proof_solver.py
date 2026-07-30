"""
Shakedown of the forcing-fragment proof solver (competition/proof_solver.py)
plus the k-bonacci placement result it rides on.

Four sections, one JSON:

  kbonacci   -- pentanacci vs hexanacci: both constants computed from companion
                polynomials, Pisot-ness checked numerically. Resolves the
                2026-07-08 doc's open question of where order-6 legitimately
                lives: the ONE-colour (attacker-live) line automaton -- the
                solver's own per-line state space -- is the hexanacci shift;
                the two-colour corpus shift stays pentanacci (line_automaton.json).
  battery    -- hand-built positions with known verdicts, solver-verified:
                open-4 (win now), broken-4 (win now), double open-3 (tau>2
                after one pair, depth-2 win), single open-3 (rail: unique
                pinned reply, then dead -- fragment refutes), radius-2 zone
                (no 6-window fits: sqrt(3) certificate refutes outright).
  cert_selftest -- random small-zone positions; wherever the certificate fires
                at the root, re-search the fragment WITHOUT it at depth 3 and
                count false prunes (must be 0).
  mined      -- positions mined from arena self-play (random/greedy pairs --
                the fork-rich generators of run_tau_lp_gap), solved at depth
                2 (quick) / 3 (full); reports forced wins found and the
                branching cull: naive candidate-pairs vs generated vs forcing.

Output: evidence/results/proof_solver.json
        evidence/figures/fig_proof_solver_cull.png
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "competition"))
import arena
import proof_solver as ps


# -- section 1: k-bonacci constants and Pisot check ---------------------------

def kbonacci_report() -> dict:
    out = {}
    for name, k in (("pentanacci", 5), ("hexanacci", 6)):
        roots = np.roots([1.0] + [-1.0] * k)
        perron = float(max(r.real for r in roots if abs(r.imag) < 1e-9))
        conj = sorted((abs(r) for r in roots), reverse=True)[1:]
        out[name] = {
            "order": k,
            "constant": perron,
            "max_conjugate_modulus": float(conj[0]),
            "is_pisot": bool(conj[0] < 1.0 - 1e-9),
        }
    out["identification"] = {
        "pentanacci_object": "two-colour no-6-run line shift -- corpus capacity, "
                             "Line A (evidence/results/line_automaton.json)",
        "hexanacci_object": "one-colour Maker-live line shift (binary words "
                            "avoiding 1^6, f(n)=sum f(n-1..n-6)) -- the proof "
                            "solver's per-line automaton, Line B",
        "note": "WIN_LENGTH=6 puts BOTH constants in play at different objects; "
                "both are Pisot (k-bonacci constants have all conjugates in the "
                "open unit disk). The 2026-07-08 doc's 3-axis coupled automaton "
                "remains a third, uncomputed object.",
    }
    # live-fraction decay of the one-colour automaton: h(n)/2^n ~ C (psi6/2)^n
    h = [1, 2, 4, 8, 16, 32]  # words of length 0..5 (all: no 1^6 possible yet)
    for n in range(6, 31):
        h.append(sum(h[-6:]))
    out["one_colour_live_fraction"] = {
        str(n): h[n] / 2 ** n for n in (6, 12, 18, 24, 30)
    }
    return out


# -- section 2: battery of known verdicts --------------------------------------

def _row(cells, player=1):
    return {c: player for c in cells}


def _classify_line(line):
    """Which mechanism the win used, for honest reporting -- 'proven' lumps
    together immediate win-now, a single tau>2 pair, and genuine multi-turn
    forcing chains, and these are very different strength claims."""
    if not line:
        return None
    tag0, _ = line[0]
    if tag0 == "A-win":
        return "immediate_win_now"
    if len(line) >= 2 and line[1] == ("D", "cannot-cover: tau>2"):
        return "single_pair_tau_gt2"
    return "multi_turn_chain"


def battery() -> list[dict]:
    """Each case checks the STATUS *and*, where the theory note makes a
    specific structural claim (exact tau, unique reply), an assertion on
    the solver's internals -- not just a string-equality label check (an
    external review found the double-open-3 case's PV has exact tau=3, not
    the tau=4 the note originally claimed for it; fixed here by computing
    the true value instead of asserting a memorised one)."""
    cases = []

    def run(name, stones, depth, expect, zone=None, note="", checks=None):
        res = ps.solve(stones, attacker=1, depth=depth, zone=zone)
        ok = res.status == expect
        detail = {}
        if checks is not None:
            try:
                detail = checks(res) or {}
                ok = ok and detail.get("pass", True)
            except Exception as e:  # noqa: BLE001 -- surface in the report, don't crash the run
                detail = {"pass": False, "error": str(e)}
                ok = False
        cases.append({
            "name": name, "depth": depth, "expected": expect,
            "got": res.status, "pass": ok,
            "mechanism": _classify_line(res.line),
            "or_nodes": res.stats.or_nodes, "root_phi": res.root_phi,
            "cap_hits": res.stats.cap_hits,
            "line": [[str(tag), str(mv)] for tag, mv in res.line][:6],
            "checks": detail, "note": note,
        })

    run("open4_win_now", _row([(i, 0) for i in range(4)]), 1, "proven",
        note="open-4 with the move completes: deficit-2 window, 2 stones")
    run("broken4_win_now", _row([(0, 0), (1, 0), (2, 0), (4, 0)]), 1, "proven",
        note="gap-4: window [-1..4] has 4 own, empties {(-1,0),(3,0)}")

    def _check_double_open3(res):
        pair = res.line[0][1]
        nxt = {**{(i, 0): 1 for i in range(3)}, **{(i, 8): 1 for i in range(3)}}
        for c in pair:
            nxt[c] = 1
        edges = ps.obligations_through(nxt, 1, pair, None)
        exact = ps.exact_tau(edges)
        alt_pair = ((3, 0), (3, 8))
        alt_nxt = {**{(i, 0): 1 for i in range(3)}, **{(i, 8): 1 for i in range(3)},
                  (3, 0): 1, (3, 8): 1}
        alt_exact = ps.exact_tau(ps.obligations_through(alt_nxt, 1, alt_pair, None))
        return {"pass": exact > 2, "chosen_pair_exact_tau": exact,
                "alt_symmetric_pair_exact_tau": alt_exact}

    run("double_open3_depth2",
        {**_row([(i, 0) for i in range(3)]), **_row([(i, 8) for i in range(3)])},
        2, "proven",
        note="one pair pushes exact tau>2 (solver's chosen pair varies by set "
             "iteration order -- checked, not assumed, below; a hand-picked "
             "symmetric pair (3,0)+(3,8) reaches exact tau=4, two disjoint "
             "min-vertex-cover-2 paths, but that is not necessarily the pair "
             "the search finds). The SAT AND-gate seed.",
        checks=_check_double_open3)

    def _check_rail_unique_reply(res):
        stones = _row([(i, 0) for i in range(3)])
        pairs = ps._forcing_pairs(stones, 1, None, 300, ps.Stats())
        tau2 = []
        for p in pairs:
            nxt = dict(stones)
            for c in p:
                nxt[c] = 1
            edges = ps.obligations_through(nxt, 1, p, None)
            tau, hitters = ps.hitting_sets_le2(edges)
            if tau == 2:
                tau2.append((p, len(hitters)))
        unique = [p for p, n in tau2 if n == 1]
        return {"pass": len(unique) > 0 and res.stats.cap_hits == 0,
                "n_tau2_candidates": len(tau2),
                "n_with_unique_reply": len(unique),
                "example_unique_reply_pair": unique[0] if unique else None}

    run("single_open3_rail", _row([(i, 0) for i in range(3)]), 3,
        "refuted_fragment",
        note="at least one forcing pair pins the defender to a UNIQUE reply "
             "(the wire step); the fragment still refutes overall (no cap "
             "hits, so the refutation is over the full uncapped candidate "
             "set at this depth, not an artifact of truncation)",
        checks=_check_rail_unique_reply)

    run("radius2_zone_cert", {(0, 0): 1}, 4, "refuted_cert",
        zone=ps.dilate([(0, 0)], 2),
        note="no 6-window fits in a radius-2 ball: Phi=0<1/9, hard refutation")

    # Regression test for the external-review finding: a self-sufficient
    # single-stone fork (tau=3 alone, 3 disjoint edges on 3 axes) paired
    # with a remote single-cell defender block. Before the _forcing_pairs
    # fix, the candidate generator only ever paired P-cells with OTHER
    # P-cells, so it never tried (fork_cell, remote_block) and returned
    # refuted_fragment on a position that is actually a forced win --
    # a real completeness bug, not a labeling issue.
    fork_stones = {}
    for i in (1, 2, 3):
        fork_stones[(i, 0)] = 1
        fork_stones[(0, i)] = 1
        fork_stones[(i, -i)] = 1
    fork_stones[(98, 0)] = 1  # walls off one side of the defender run
    for i in range(99, 103):
        fork_stones[(i, 0)] = 2

    def _check_fork_remote_block(res):
        pair = res.line[0][1] if res.line and res.line[0][0] == "A" else None
        uses_remote_block = pair is not None and any(
            c in ((103, 0), (104, 0)) for c in pair)
        return {"pass": uses_remote_block, "chosen_pair": pair}

    run("fork_plus_remote_block_regression", fork_stones, 2, "proven",
        note="reviewer counterexample, 2026-07-20: triple fork at (0,0) "
             "(exact tau=3 from ONE stone) + defender's single remaining "
             "win-now window {(103,0),(104,0)} blockable by either cell; "
             "was refuted_fragment before the _forcing_pairs fix",
        checks=_check_fork_remote_block)

    return cases


# -- section 3: certificate soundness self-test ---------------------------------

def cert_selftest(n_samples: int, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    zone = ps.dilate([(0, 0)], 4)
    zone_list = sorted(zone)
    fired, checked, false_prunes = 0, 0, 0
    for _ in range(n_samples):
        # defender-dense: most windows must die or the potential never drops
        # below 1/9 and the certificate is never exercised
        n_att = int(rng.integers(1, 7))
        n_def = int(rng.integers(8, 26))
        idx = rng.choice(len(zone_list), size=n_att + n_def, replace=False)
        stones = {}
        for j, i in enumerate(idx):
            stones[zone_list[i]] = 1 if j < n_att else 2
        phi = ps.beck_phi(stones, 1, zone)
        checked += 1
        if phi < ps.CERT_THRESHOLD_OR:
            fired += 1
            res = ps.solve(stones, 1, depth=3, zone=zone, use_cert=False)
            if res.status == "proven":
                false_prunes += 1
    return {
        "n_samples": checked, "root_fires": fired, "false_prunes": false_prunes,
        "note": "cross-checked against the depth-3 fragment only -- the "
                "certificate claims more (all strategies, any depth); the "
                "analytic proof is in the theory note, this is the smoke test",
    }


# -- section 4: mined positions -------------------------------------------------

def mine_positions(n_games: int, seed_base: int, max_stones: int = 50):
    """Fork-rich generators, as in run_tau_lp_gap: random bots never block, so
    tau>2 structures actually accumulate; greedy_offence builds dense threat
    fields. Sampled mid-game, normalised to attacker-full-turn."""
    positions = []
    for g in range(n_games):
        s = arena.State()
        if g % 3 == 0:
            a, b = arena.random_bot(seed=seed_base + g), arena.random_bot(seed=seed_base + 5000 + g)
        elif g % 3 == 1:
            a, b = arena.greedy_offence(), arena.greedy_offence()
        else:
            a, b = arena.random_bot(seed=seed_base + g), arena.greedy_offence()
        players = {1: a, 2: b}
        placements = 0
        while s.winner is None and placements < 90:
            mv = players[s.turn](s)
            if mv in s.stones:
                break
            s = arena.place(s, *mv)
            placements += 1
            if 12 <= len(s.stones) <= max_stones and placements % 4 == 0:
                positions.append(dict(s.stones))
    return positions


def mined_scan(n_games: int, depth: int, seed: int, max_pairs: int) -> dict:
    positions = mine_positions(n_games, seed)
    agg = {"n_positions": len(positions), "depth": depth, "proven": 0,
           "refuted_fragment": 0, "unknown": 0, "or_nodes": 0, "pair_naive": 0,
           "pair_generated": 0, "pair_forcing": 0, "cap_hits": 0,
           "defender_counterwins": 0, "proven_examples": [],
           "proven_mechanism": {"immediate_win_now": 0, "single_pair_tau_gt2": 0,
                                "multi_turn_chain": 0}}
    per_root = []
    for pi, pos in enumerate(positions):
        for attacker in (1, 2):
            res = ps.solve(pos, attacker, depth=depth, zone=None,
                           use_cert=False, max_pairs=max_pairs)
            st = res.stats
            agg[res.status] = agg.get(res.status, 0) + 1
            for k in ("or_nodes", "pair_naive", "pair_generated",
                      "pair_forcing", "cap_hits", "defender_counterwins"):
                agg[k] += getattr(st, k)
            if st.or_nodes:
                per_root.append((st.pair_naive / st.or_nodes,
                                 st.pair_generated / st.or_nodes,
                                 st.pair_forcing / st.or_nodes))
            if res.status == "proven":
                mech = _classify_line(res.line)
                agg["proven_mechanism"][mech] = agg["proven_mechanism"].get(mech, 0) + 1
                if len(agg["proven_examples"]) < 5:
                    agg["proven_examples"].append({
                        "position_index": pi, "attacker": attacker,
                        "n_stones": len(pos), "mechanism": mech,
                        "line": [[str(t), str(m)] for t, m in res.line][:8],
                    })
    agg["cull"] = {
        "naive_pairs_per_or_node": agg["pair_naive"] / max(1, agg["or_nodes"]),
        "generated_pairs_per_or_node": agg["pair_generated"] / max(1, agg["or_nodes"]),
        "forcing_pairs_per_or_node": agg["pair_forcing"] / max(1, agg["or_nodes"]),
        "generated_over_naive": agg["pair_generated"] / max(1, agg["pair_naive"]),
        "forcing_over_naive": agg["pair_forcing"] / max(1, agg["pair_naive"]),
        "note": "'naive' = C(arena.candidates,2), i.e. all pairs from cells "
                "ADJACENT to an existing stone (arena.py's own move generator "
                "baseline) -- not literally every legal cell on the infinite "
                "board. The ratio below is a reduction relative to that "
                "baseline, not an absolute search-space bound.",
    }
    if agg["unknown"]:
        agg["cull"]["unknown_fraction_of_negative"] = agg["unknown"] / max(
            1, agg["unknown"] + agg["refuted_fragment"])
    agg["_per_root"] = per_root
    return agg


# -- figure ----------------------------------------------------------------------

def make_figure(kb: dict, mined: dict, path: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))

    ax = axes[0]
    theta = np.linspace(0, 2 * np.pi, 200)
    ax.plot(np.cos(theta), np.sin(theta), color="gray", lw=0.8, ls="--")
    for name, k, color in (("pentanacci (2-colour shift)", 5, "#cc6677"),
                           ("hexanacci (1-colour shift)", 6, "#4477aa")):
        roots = np.roots([1.0] + [-1.0] * k)
        ax.scatter(roots.real, roots.imag, s=30, color=color, label=name, zorder=3)
    ax.axhline(0, color="lightgray", lw=0.5)
    ax.set_aspect("equal")
    ax.set_title("k-bonacci roots: Perron outside, conjugates inside\n(Pisot for both)")
    ax.legend(fontsize=8, loc="upper left")

    ax = axes[1]
    pr = mined.get("_per_root", [])
    if pr:
        naive, gen, forcing = zip(*pr)
        ax.scatter(naive, gen, s=14, alpha=0.5, color="#cc6677",
                   label="generated (fragment)")
        ax.scatter(naive, forcing, s=14, alpha=0.5, color="#4477aa",
                   label="forcing (tau>=2)")
        lim = max(max(naive), 10)
        ax.plot([1, lim], [1, lim], "k--", lw=0.8, label="no cull")
        ax.set_xscale("log"); ax.set_yscale("symlog")
        ax.set_xlabel("naive candidate pairs / OR node")
        ax.set_ylabel("pairs after cull / OR node")
    ax.set_title("Forcing-fragment branching cull (mined positions)")
    ax.legend(fontsize=8)

    fig.tight_layout()
    fig.savefig(path, dpi=150)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--depth", type=int, default=None)
    args = ap.parse_args()
    depth = args.depth or (2 if args.quick else 3)
    n_games = 8 if args.quick else 30
    n_cert = 120 if args.quick else 400

    t0 = time.time()
    kb = kbonacci_report()
    bat = battery()
    cert = cert_selftest(n_cert, args.seed + 1)
    mined = mined_scan(n_games, depth, args.seed, max_pairs=150)

    per_root = mined.pop("_per_root")
    summary = {
        "kbonacci": kb,
        "battery": bat,
        "battery_all_pass": all(c["pass"] for c in bat),
        "cert_selftest": cert,
        "mined": mined,
        "seed": args.seed,
        "quick": args.quick,
        "wall_time_s": round(time.time() - t0, 1),
    }
    print(json.dumps({k: v for k, v in summary.items() if k != "mined"}, indent=2))
    print(json.dumps({"mined": {k: v for k, v in mined.items()
                                if k != "proven_examples"}}, indent=2))

    out = ROOT / "evidence" / "results" / "proof_solver.json"
    out.write_text(json.dumps(summary, indent=2))
    print(f"[saved] {out}")

    mined["_per_root"] = per_root
    figp = ROOT / "evidence" / "figures" / "fig_proof_solver_cull.png"
    make_figure(kb, mined, figp)
    print(f"[saved] {figp}")

    if not summary["battery_all_pass"] or cert["false_prunes"]:
        print("!! BATTERY FAILURE OR FALSE CERT PRUNE -- do not trust results")
        sys.exit(1)


if __name__ == "__main__":
    main()
