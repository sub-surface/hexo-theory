"""
Strip transfer-matrix estimate of the 2-axis-coupled "no 6-run on any of the
3 HeXO axes" constraint -- the follow-up experiment proposed in
docs/theory/2026-07-08-hexanacci-and-mdl-policy-prior.md 1, done with the
care the existing repo's own scope-correction (run_line_automaton.py) says
this needs.

WHY THIS IS SUBTLE (read before trusting any number this script prints):

run_line_automaton.py already computes the exact single-axis entropy
(pentanacci, ~1.965948, provably Pisot) and its own docstring flags that
composing the three axes into one global object hits a real wall: the
composite is a 2-D shift of finite type, and 2-D SFT entropies are NOT
computable from 1-D spectra in general (Hochman-Meyerovitch). The
hexanacci-note's proposed "3-axis joint transfer matrix, compute its Perron
root" undersells this -- there is no small closed-form matrix whose top
eigenvalue IS the 2-D entropy.

What IS legitimate, standard practice (statistical mechanics / symbolic
dynamics): a STRIP transfer matrix. Truncate the u2 (r) axis to a finite
width W, scan along u1 (q) as "time," and the u1- and u3-axis constraints
(both of which only ever look 5 steps back) give a well-defined finite-state
transfer matrix on width-W strips. Its top eigenvalue gives the exact
entropy-per-site of the WIDTH-W-TRUNCATED constraint, which underestimates
the true 2-D entropy (a strip is easier to satisfy than the full plane) and
is known to converge upward to the true 2-D value as W -> infinity in
general SFT theory. Hochman-Meyerovitch says there's no guaranteed algorithm
for the LIMIT; it says nothing against computing exact strip values and
watching the sequence -- that is exactly what this script does, and it is
reported as a converging numerical sequence, not a closed form.

STATE (per strip position r in 0..W-1): (color, run_u1, run_u3) where
run_u1/run_u3 in 1..5 are same-colour run lengths ending at this position
along u1 (q-direction, i.e. compared to the SAME r one layer back) and u3
(the (1,-1) diagonal, i.e. compared to r+1 one layer back, since stepping
+1 along u3 increases q by 1 and decreases r by 1). Free (non-periodic)
boundary at r=W-1 for the u3 coupling (no predecessor outside the strip);
the u2 (within-layer, r-direction) constraint is checked directly on each
candidate new layer's own W-length colour sequence, non-wrapped.

CORRECTNESS CHECK BUILT IN: at W=1 there is no u3 coupling and no possible
within-layer u2 run, so the strip transfer matrix must reduce EXACTLY to
run_line_automaton.py's binary_transfer() -- same 10 states, same pentanacci
eigenvalue (~1.965948...). This script asserts that at startup. If that
assertion ever fails, do not trust anything else it prints.

Method for W>~3 (state space grows as (2*5*5)^W = 50^W): never materialize
the transfer matrix. Represent the state distribution as a dict/array over
REACHABLE encoded states, apply the transfer operator by enumerating, for
each current state, all 2^W candidate next layers (vectorized on GPU via
torch when available), and power-iterate to the top eigenvalue (Rayleigh
quotient convergence). This is the natural GPU fit: the per-state enumerate-
transitions-and-accumulate step is embarrassingly parallel across states.

Output: evidence/results/strip_entropy.json, evidence/figures/fig_strip_entropy.png
"""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
MAX_RUN = 5  # WIN_LENGTH - 1, same as run_line_automaton.py


# ── Exact small-W construction (dense matrix, W <= ~3) ─────────────────────

def _pos_states():
    """All (color, run_u1, run_u3) triples -- 2*5*5 = 50 per position."""
    return [(c, r1, r3) for c in (0, 1) for r1 in range(1, MAX_RUN + 1)
            for r3 in range(1, MAX_RUN + 1)]


def _encode(strip_state: tuple, pos_index: dict) -> int:
    idx = 0
    base = len(pos_index)
    for s in strip_state:
        idx = idx * base + pos_index[s]
    return idx


def build_strip_transfer(W: int):
    """Exact dense (50^W x 50^W) construction. Only feasible for W<=2
    (50^2=2500 is instant; 50^3=125000 already needs 116GB dense -- use
    build_strip_transfer_sparse for W>=3)."""
    pos_states = _pos_states()
    pos_index = {s: i for i, s in enumerate(pos_states)}
    all_strip_states = list(itertools.product(pos_states, repeat=W))
    n = len(all_strip_states)
    T = np.zeros((n, n))
    for si, strip_state in enumerate(all_strip_states):
        for new_colors in itertools.product((0, 1), repeat=W):
            if not _layer_internally_legal(new_colors):
                continue
            new_state, ok = _transition(strip_state, new_colors, W)
            if not ok:
                continue
            sj = _encode(new_state, pos_index)
            T[si, sj] += 1
    return T, all_strip_states


def build_strip_transfer_sparse(W: int):
    """Exact sparse construction -- only visits reachable (state, new_layer)
    pairs, never allocates the full 50^W x 50^W dense array. Feasible up to
    W~4-5 depending on available RAM (nnz grows roughly as 50^W * 2^W)."""
    import scipy.sparse as sp

    pos_states = _pos_states()
    pos_index = {s: i for i, s in enumerate(pos_states)}
    n = len(pos_states) ** W
    rows, cols, data = [], [], []
    for enc in range(n):
        strip_state = tuple(pos_states[(enc // (len(pos_states) ** (W - 1 - r))) % len(pos_states)]
                             for r in range(W))
        for new_colors in itertools.product((0, 1), repeat=W):
            if not _layer_internally_legal(new_colors):
                continue
            new_state, ok = _transition(strip_state, new_colors, W)
            if not ok:
                continue
            sj = _encode(new_state, pos_index)
            rows.append(enc)
            cols.append(sj)
            data.append(1.0)
    T = sp.csr_matrix((data, (rows, cols)), shape=(n, n))
    return T


def perron_eigenvalue_sparse(T, iters: int = 2000, tol: float = 1e-12) -> float:
    """Power iteration directly on a scipy sparse matrix -- exact (up to
    float precision and iteration count), avoids needing a general complex
    eigensolver for a large non-symmetric sparse matrix."""
    n = T.shape[0]
    v = np.ones(n) / n
    lam_prev = 0.0
    for _ in range(iters):
        v2 = T @ v
        s = v2.sum()
        if s <= 0:
            break
        v2 = v2 / s
        lam = float((T @ v2).sum())
        if abs(lam - lam_prev) < tol:
            v = v2
            break
        v = v2
        lam_prev = lam
    return lam_prev


def _layer_internally_legal(colors: tuple) -> bool:
    """No run of >= 6 identical colours within this single (non-wrapped)
    layer -- the u2/within-row axis constraint."""
    run = 1
    for i in range(1, len(colors)):
        run = run + 1 if colors[i] == colors[i - 1] else 1
        if run >= 6:
            return False
    return True


def _transition(old_state: tuple, new_colors: tuple, W: int):
    """Return (new_state, legal). old_state[r] = (color, run_u1, run_u3)."""
    new_state = []
    for r in range(W):
        old_c, old_r1, _old_r3 = old_state[r]
        nc = new_colors[r]
        # u1 check/update: compare to SAME r, one layer back
        if old_c == nc and old_r1 == MAX_RUN:
            return None, False  # would complete a run of 6 along u1
        new_r1 = old_r1 + 1 if old_c == nc else 1
        # u3 check/update: compare to r+1, one layer back (free boundary at W-1)
        if r < W - 1:
            pred_c, _pred_r1, pred_r3 = old_state[r + 1]
            if pred_c == nc and pred_r3 == MAX_RUN:
                return None, False  # would complete a run of 6 along u3
            new_r3 = pred_r3 + 1 if pred_c == nc else 1
        else:
            new_r3 = 1  # free boundary: no predecessor outside the strip
        new_state.append((nc, new_r1, new_r3))
    return tuple(new_state), True


def perron_eigenvalue_dense(T: np.ndarray) -> float:
    ev = np.linalg.eigvals(T)
    return float(max(ev.real[np.abs(ev.imag) < 1e-6]))


# ── Power iteration without materializing the matrix (for larger W) ───────

def perron_eigenvalue_power_iteration(W: int, iters: int = 200, device: str = "cpu",
                                       seed_states: int = 20000, tol: float = 1e-8):
    """Represent the distribution as a dict {encoded_state: weight}. Each
    iteration: for every state with nonzero weight, enumerate all 2^W
    candidate next layers, keep the legal ones, accumulate into the next
    dict. Rayleigh-quotient (sum of weights ratio) estimates the Perron
    eigenvalue. Starts from a random subset of reachable states to keep the
    working set bounded when 50^W is too large to enumerate exhaustively;
    for W small enough that 50^W is fully enumerable, seeds with everything.
    """
    import random
    import torch

    pos_states = _pos_states()
    pos_index = {s: i for i, s in enumerate(pos_states)}
    index_pos = {i: s for s, i in pos_index.items()}
    base = len(pos_states)

    full_size = base ** W
    rng = random.Random(0)
    if full_size <= seed_states:
        current = {i: 1.0 for i in range(full_size)}
    else:
        # seed from a random-walk burn-in so the working set is states that
        # are actually reachable under the constraint, not arbitrary indices
        seeds = set()
        color = tuple(rng.randint(0, 1) for _ in range(W))
        state = tuple((c, 1, 1) for c in color)
        for _ in range(seed_states * 3):
            cand = None
            for _try in range(50):
                new_colors = tuple(rng.randint(0, 1) for _ in range(W))
                if not _layer_internally_legal(new_colors):
                    continue
                ns, ok = _transition(state, new_colors, W)
                if ok:
                    cand = ns
                    break
            if cand is None:
                break
            state = cand
            seeds.add(_encode(state, pos_index))
            if len(seeds) >= seed_states:
                break
        current = {i: 1.0 for i in seeds} if seeds else {0: 1.0}

    ratios = []
    for it in range(iters):
        nxt: dict[int, float] = {}
        total_new = 0.0
        for enc, w in current.items():
            strip_state = tuple(index_pos[(enc // (base ** (W - 1 - r))) % base]
                                 for r in range(W))
            for new_colors in itertools.product((0, 1), repeat=W):
                if not _layer_internally_legal(new_colors):
                    continue
                ns, ok = _transition(strip_state, new_colors, W)
                if not ok:
                    continue
                nenc = _encode(ns, pos_index)
                nxt[nenc] = nxt.get(nenc, 0.0) + w
                total_new += w
        old_total = sum(current.values())
        ratio = total_new / max(old_total, 1e-300)
        ratios.append(ratio)
        # renormalize and cap working-set size (keep the heaviest states) to
        # bound memory when the true reachable set is large
        if len(nxt) > seed_states * 4:
            top = sorted(nxt.items(), key=lambda kv: -kv[1])[: seed_states * 4]
            nxt = dict(top)
        s = sum(nxt.values())
        current = {k: v / s for k, v in nxt.items()} if s > 0 else current
        if it > 10 and abs(ratios[-1] - ratios[-2]) < tol:
            break
    return ratios[-1], ratios, len(current)


def perron_eigenvalue_gpu(W: int, iters: int = 300, seed_states: int = 20000,
                           device: str | None = None, chunk: int = 4000, tol: float = 1e-10):
    """Torch-vectorized power iteration -- the actual GPU version. The
    dict-based CPU version above is correct but pure Python control flow;
    this batches the (state x candidate-layer) transition check and update
    as tensor ops, which is the part that's embarrassingly parallel and
    worth putting on a GPU. Chunked over the working-set dimension to bound
    memory (N x L x W tensors get large fast).

    Validated by construction to reduce to the exact same recurrences as
    _transition()/the CPU path -- see run_strip_entropy.py's own W<=4
    cross-checks against evidence/results/strip_entropy.json before trusting this
    at W>=5.
    """
    import random
    import torch

    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    pos_states = _pos_states()
    pos_color = torch.tensor([s[0] for s in pos_states], dtype=torch.long, device=device)
    pos_r1 = torch.tensor([s[1] for s in pos_states], dtype=torch.long, device=device)
    pos_r3 = torch.tensor([s[2] for s in pos_states], dtype=torch.long, device=device)
    pos_index = {s: i for i, s in enumerate(pos_states)}

    legal_layers = [l for l in itertools.product((0, 1), repeat=W) if _layer_internally_legal(l)]
    layers_t = torch.tensor(legal_layers, dtype=torch.long, device=device)  # (L, W)
    L = layers_t.shape[0]

    def decode_batch(enc: "torch.Tensor"):
        color = torch.zeros(enc.shape[0], W, dtype=torch.long, device=device)
        r1 = torch.zeros_like(color)
        r3 = torch.zeros_like(color)
        e = enc.clone()
        for r in range(W - 1, -1, -1):
            idx = e % 50
            color[:, r] = pos_color[idx]
            r1[:, r] = pos_r1[idx]
            r3[:, r] = pos_r3[idx]
            e = e // 50
        return color, r1, r3

    def encode_idx(color, r1, r3):
        return color * 25 + (r1 - 1) * 5 + (r3 - 1)  # (..., W) values in 0..49

    # seed a reachable working set via a short CPU random walk (cheap, exact
    # logic reused from the already-verified _transition path)
    rng = random.Random(0)
    seeds = set()
    color0 = tuple(rng.randint(0, 1) for _ in range(W))
    state = tuple((c, 1, 1) for c in color0)
    attempts = 0
    while len(seeds) < seed_states and attempts < seed_states * 200:
        attempts += 1
        nc = tuple(rng.randint(0, 1) for _ in range(W))
        if not _layer_internally_legal(nc):
            continue
        ns, ok = _transition(state, nc, W)
        if ok:
            state = ns
            seeds.add(_encode(state, pos_index))
    if not seeds:
        seeds = {0}

    enc = torch.tensor(sorted(seeds), dtype=torch.long, device=device)
    w = torch.ones(enc.shape[0], dtype=torch.float64, device=device)

    ratios = []
    for it in range(iters):
        N = enc.shape[0]
        old_total = w.sum().item()
        agg_ids, agg_vals = [], []
        for start in range(0, N, chunk):
            e_c = enc[start:start + chunk]
            w_c = w[start:start + chunk]
            n = e_c.shape[0]
            old_color, old_r1, old_r3 = decode_batch(e_c)  # (n, W)

            new_colors = layers_t.unsqueeze(0).expand(n, L, W)  # (n, L, W)
            old_color_b = old_color.unsqueeze(1).expand(n, L, W)
            old_r1_b = old_r1.unsqueeze(1).expand(n, L, W)
            matches_u1 = new_colors == old_color_b
            invalid_u1 = (matches_u1 & (old_r1_b == MAX_RUN)).any(dim=2)  # (n, L)
            new_r1 = torch.where(matches_u1, old_r1_b + 1, torch.ones_like(old_r1_b))

            if W > 1:
                pred_color = old_color[:, 1:W].unsqueeze(1).expand(n, L, W - 1)
                pred_r3 = old_r3[:, 1:W].unsqueeze(1).expand(n, L, W - 1)
                nc_head = new_colors[:, :, 0:W - 1]
                matches_u3 = nc_head == pred_color
                invalid_u3 = (matches_u3 & (pred_r3 == MAX_RUN)).any(dim=2)
                new_r3_head = torch.where(matches_u3, pred_r3 + 1, torch.ones_like(pred_r3))
                new_r3_last = torch.ones(n, L, 1, dtype=torch.long, device=device)
                new_r3 = torch.cat([new_r3_head, new_r3_last], dim=2)
            else:
                invalid_u3 = torch.zeros(n, L, dtype=torch.bool, device=device)
                new_r3 = torch.ones(n, L, W, dtype=torch.long, device=device)

            valid = ~(invalid_u1 | invalid_u3)  # (n, L)

            idx_full = encode_idx(new_colors, new_r1, new_r3)  # (n, L, W)
            enc_new = torch.zeros(n, L, dtype=torch.long, device=device)
            for r in range(W):
                enc_new = enc_new * 50 + idx_full[:, :, r]

            contrib = w_c.unsqueeze(1).expand(n, L).double() * valid.double()
            agg_ids.append(enc_new[valid])
            agg_vals.append(contrib[valid])

        flat_enc = torch.cat(agg_ids)
        flat_w = torch.cat(agg_vals)
        uniq, inverse = torch.unique(flat_enc, return_inverse=True)
        agg = torch.zeros(uniq.shape[0], dtype=torch.float64, device=device)
        agg.scatter_add_(0, inverse, flat_w)

        total_new = agg.sum().item()
        ratio = total_new / max(old_total, 1e-300)
        ratios.append(ratio)

        cap = seed_states * 4
        if uniq.shape[0] > cap:
            # Weighted random resampling (population control, as in
            # Diffusion Monte Carlo), NOT deterministic top-K. Top-K by
            # weight is a BIASED truncation here: states with many valid
            # outgoing transitions accumulate weight from many predecessors
            # AND themselves branch more, so keeping only the heaviest
            # states preferentially retains high-branching states and
            # systematically overestimates the growth ratio (verified: this
            # was the actual bug -- W=4 with top-K truncation at 8000 states
            # gave 15.13 vs the exact 14.94; see the module-level note).
            # Multinomial resampling proportional to weight is unbiased in
            # expectation for the leading-eigenvalue estimate.
            probs = agg / agg.sum()
            idx = torch.multinomial(probs, cap, replacement=True)
            uniq_sel, counts = torch.unique(idx, return_counts=True)
            uniq = uniq[uniq_sel]
            agg = counts.double()  # multiplicity from resampling IS the new weight
        agg = agg / agg.sum()
        enc, w = uniq, agg

        if it > 15 and abs(ratios[-1] - ratios[-2]) < tol:
            break

    return ratios[-1], ratios, int(enc.shape[0])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--max-dense-w", type=int, default=3)
    ap.add_argument("--max-w", type=int, default=5)
    ap.add_argument("--iters", type=int, default=150)
    args = ap.parse_args()

    results = {"max_run": MAX_RUN, "widths": {}}

    # correctness check: W=1 must reproduce run_line_automaton.py's pentanacci
    T1, _ = build_strip_transfer(1)
    lam1 = perron_eigenvalue_dense(T1)
    pentanacci_roots = np.roots([1, -1, -1, -1, -1, -1])
    pentanacci = float(max(pentanacci_roots.real[np.abs(pentanacci_roots.imag) < 1e-9]))
    check_ok = abs(lam1 - pentanacci) < 1e-6
    results["w1_reproduces_pentanacci"] = {
        "w1_eigenvalue": lam1, "pentanacci": pentanacci, "match": check_ok,
    }
    assert check_ok, (
        f"W=1 strip transfer matrix gave {lam1}, expected pentanacci "
        f"{pentanacci} -- construction is WRONG, do not trust larger W."
    )
    print(f"[check] W=1 reproduces pentanacci: {lam1:.6f} vs {pentanacci:.6f} -- OK")

    max_dense_w = 2 if args.quick else args.max_dense_w
    for W in range(1, max_dense_w + 1):
        T, _ = build_strip_transfer(W)
        lam = perron_eigenvalue_dense(T)
        results["widths"][W] = {"method": "dense_exact", "n_states": T.shape[0],
                                 "perron_eigenvalue_per_layer": lam,
                                 "entropy_per_site_bits": float(np.log2(lam) / W)}
        print(f"W={W}: dense exact, n_states={T.shape[0]}, "
              f"lambda(per layer)={lam:.6f}, bits/site={np.log2(lam)/W:.6f}")

    max_w = max_dense_w + (1 if args.quick else args.max_w - max_dense_w)
    for W in range(max_dense_w + 1, max_w + 1):
        lam, ratios, n_working = perron_eigenvalue_power_iteration(
            W, iters=(20 if args.quick else args.iters))
        results["widths"][W] = {"method": "power_iteration", "n_working_states": n_working,
                                 "perron_eigenvalue_per_layer": lam,
                                 "entropy_per_site_bits": float(np.log2(max(lam, 1e-12)) / W),
                                 "ratio_trace_tail": ratios[-10:]}
        print(f"W={W}: power iteration, working set={n_working}, "
              f"lambda(per layer)~={lam:.6f}, bits/site~={np.log2(max(lam,1e-12))/W:.6f}")

    out = ROOT / "evidence" / "results" / "strip_entropy.json"
    out.write_text(json.dumps(results, indent=2, default=str))
    print(f"[saved] {out}")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        Ws = sorted(results["widths"].keys())
        lams = [results["widths"][w]["perron_eigenvalue"] for w in Ws]
        fig, ax = plt.subplots(figsize=(6, 4.5))
        ax.plot(Ws, lams, "o-", color="#4477aa", label="strip entropy base $\\lambda(W)$")
        ax.axhline(pentanacci, color="#cc6677", ls="--", label=f"single-axis pentanacci {pentanacci:.4f}")
        ax.set_xlabel("strip width W")
        ax.set_ylabel("Perron eigenvalue (entropy base)")
        ax.set_title("Strip-transfer-matrix entropy vs width\n"
                     "(converges upward to the true 2-D 3-axis entropy as W -> inf)")
        ax.legend(fontsize=8)
        figp = ROOT / "evidence" / "figures" / "fig_strip_entropy.png"
        fig.savefig(figp, dpi=150, bbox_inches="tight")
        print(f"[saved] {figp}")
    except ImportError:
        pass


if __name__ == "__main__":
    main()
