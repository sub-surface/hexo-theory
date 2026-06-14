"""
HexGo Theory Lab
Run:  marimo edit lab.py

Sections
  0  Imports & setup
  1  Board visualiser
  2  D6 orbit panel
  3  Programme A  -- Paradox 1: information from deterministic computation
  4  Programme D  -- Pisot spectroscope: S_T(N) scaling
  5  Programme E  -- MDL Pareto frontier
  6  Time-resolved H_T
  7  Pair correlation g(r)
  8  Programme F  -- Epiplexity emergence gap (Finzi Def. 14)
  9  Notes / scratch
"""

import marimo

__generated_with = "0.23.1"
app = marimo.App(width="medium", app_title="HexGo Theory Lab")


@app.cell
def _setup():
    import sys, math, random
    from pathlib import Path

    _ROOT = Path(__file__).resolve().parent
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))

    import numpy as np
    import matplotlib.pyplot as plt
    import matplotlib as mpl
    mpl.rcParams.update({
        "figure.facecolor": "#1a1a2e",
        "axes.facecolor":   "#1a1a2e",
        "axes.edgecolor":   "#aaa",
        "axes.labelcolor":  "#ccc",
        "xtick.color":      "#ccc",
        "ytick.color":      "#ccc",
        "text.color":       "#eee",
        "grid.color":       "#333",
        "legend.facecolor": "#222",
        "legend.edgecolor": "#444",
    })

    from hexgo import (HexGame, RandomAgent, EisensteinGreedyAgent,
                       ForkAwareAgent, PotentialGradientAgent, ComboAgent)
    from hexgo.epiplexity import (generate, Corpus, measure, tokens,
                                   program_length, agent_cross_entropy,
                                   MarkovObserver)
    from hexgo.analysis   import (potential_map, threat_cells, fork_cells,
                                   pair_correlation)
    from hexgo.viz        import draw_board, d6_panel, play

    CORPORA = _ROOT / "corpora"
    RESULTS = _ROOT / "results"
    CORPORA.mkdir(exist_ok=True)
    RESULTS.mkdir(exist_ok=True)

    AGENTS = {
        "random":  lambda: RandomAgent(),
        "greedy":  lambda: EisensteinGreedyAgent("greedy", defensive=True),
        "fork_a4": lambda: ForkAwareAgent("fork_a4", alpha=4.0),
        "potgrad": lambda: PotentialGradientAgent("potgrad"),
        "combo":   lambda: ComboAgent("combo"),
    }

    def corpus(name, n=200, seed=42):
        p = CORPORA / f"{name}_N{n}.pkl.gz"
        if p.exists():
            return Corpus.load(p)
        c = generate(AGENTS[name], AGENTS[name], n, seed)
        c.save(p)
        return c

    return (
        AGENTS,
        Corpus,
        MarkovObserver,
        agent_cross_entropy,
        corpus,
        draw_board,
        math,
        measure,
        np,
        pair_correlation,
        play,
        plt,
        program_length,
        tokens,
    )


@app.cell
def _viz_header():
    return


@app.cell
def _viz_controls(mo):
    _matchups = {
        "combo vs greedy":   ("combo",   "greedy"),
        "combo vs combo":    ("combo",   "combo"),
        "potgrad vs greedy": ("potgrad", "greedy"),
        "fork_a4 vs greedy": ("fork_a4", "greedy"),
        "random vs random":  ("random",  "random"),
    }
    _dd   = mo.ui.dropdown(list(_matchups), value="combo vs greedy", label="matchup")
    _nmv  = mo.ui.slider(4, 80, value=32, label="moves")
    _seed = mo.ui.number(0, 9999, value=2026, label="seed")
    _btn  = mo.ui.run_button(label="play")
    _pot  = mo.ui.checkbox(True, label="potential heatmap")
    _thr  = mo.ui.checkbox(True, label="threats")
    _frk  = mo.ui.checkbox(True, label="forks")
    mo.hstack([_dd, _nmv, _seed, _pot, _thr, _frk, _btn], gap="1rem")
    return


@app.cell
def _viz_board(AGENTS, draw_board, play, plt):
    _a, _b = _matchups[_dd.value]
    _g = play(AGENTS[_a], AGENTS[_b], max_moves=_nmv.value, seed=_seed.value)
    _fig, _ax = plt.subplots(figsize=(7, 6.3))
    draw_board(_g, _ax,
               show_potential=_pot.value,
               show_threats=_thr.value,
               show_forks=_frk.value,
               title=f"{_a} vs {_b}  |  "
                     f"{'P'+str(_g.winner)+' wins' if _g.winner else 'ongoing'}  |  "
                     f"{len(_g.move_history)} moves")
    plt.tight_layout()
    return


@app.cell
def _d6_header():
    return


@app.cell
def _d6_fig():
    return


@app.cell
def _A_header():
    return


@app.cell
def _A_measure(AGENTS, corpus, measure, np, plt, program_length):
    _results = {}
    for _nm in ["random", "greedy", "fork_a4", "potgrad", "combo"]:
        _c = corpus(_nm, n=200)
        _r = measure(_c, name=_nm)
        _results[_nm] = {
            "H_markov": _r.markov_H,
            "H_gzip":   _r.gzip_H,
            "S_markov": _r.markov_S,
            "prog":     program_length(AGENTS[_nm]()),
        }

    _names  = list(_results)
    _Hm     = [_results[n]["H_markov"] for n in _names]
    _Hgz    = [_results[n]["H_gzip"]   for n in _names]
    _cols   = ["#666", "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]
    _x      = np.arange(len(_names))

    _fig, (_ax1, _ax2) = plt.subplots(1, 2, figsize=(13, 4.8))

    _ax1.bar(_x - .18, _Hm,  .36, label="Markov-3", color=_cols)
    _ax1.bar(_x + .18, _Hgz, .36, label="gzip",     color=_cols, alpha=.5, hatch="//")
    _ax1.set_xticks(_x); _ax1.set_xticklabels(_names, rotation=12)
    _ax1.set_ylabel("bits / move")
    _ax1.set_title("Cross-entropy H_T by agent corpus")
    _ax1.grid(alpha=.3, axis="y"); _ax1.legend()

    _Ps = [_results[n]["prog"] for n in _names]
    _ax2.scatter(_Ps, _Hm, s=120, c=_cols, edgecolor="white", lw=.7, zorder=3)
    for _xi, _yi, _ni in zip(_Ps, _Hm, _names):
        _ax2.annotate(_ni, (_xi, _yi), textcoords="offset points",
                      xytext=(6, 4), fontsize=9)
    _ax2.set_xlabel("|P| gzipped source (bytes)")
    _ax2.set_ylabel("H_T (bits/move)")
    _ax2.set_title("Programme A snapshot in MDL space")
    _ax2.grid(alpha=.3)

    plt.tight_layout()
    return


@app.cell
def _A_gate():
    _hr  = _results["random"]["H_markov"]
    _hc  = _results["combo"]["H_markov"]
    _gap = _hr / max(_hc, 1e-3)
    return


@app.cell
def _D_header():
    return


@app.cell
def _D_measure(corpus, measure, np, plt):
    _sizes   = [50, 100, 200, 500, 1000]
    _scaling = {"random": [], "greedy": [], "combo": []}

    for _dn in _scaling:
        for _ds in _sizes:
            _dc = corpus(_dn, n=_ds, seed=7)
            _dr = measure(_dc, name=_dn)
            _scaling[_dn].append({"N": _ds, "H": _dr.markov_H, "gz": _dr.gzip_total})

    _dcols = {"random": "#666", "greedy": "#1f77b4", "combo": "#d62728"}
    _dmks  = {"random": "o",    "greedy": "s",       "combo": "^"}

    _fig, (_ax1, _ax2) = plt.subplots(1, 2, figsize=(13, 4.8))

    for _dn, _rows in _scaling.items():
        _Ns = np.array([r["N"]  for r in _rows])
        _H  = np.array([r["H"]  for r in _rows])
        _gz = np.array([r["gz"] for r in _rows])
        _ax1.plot(_Ns, _H,  marker=_dmks[_dn], color=_dcols[_dn], label=_dn)
        _ax2.plot(_Ns, _gz, marker=_dmks[_dn], color=_dcols[_dn], label=_dn)
        if len(_Ns) >= 2:
            _sl, _ = np.polyfit(np.log10(_Ns), np.log10(_gz), 1)
            _lam   = 10**(1/_sl) if _sl > 0 else float("nan")
            _ax2.annotate(
                f"{_dn}  slope={_sl:.2f}  (lam~{_lam:.3f})",
                xy=(.03, .92 - .09 * list(_scaling).index(_dn)),
                xycoords="axes fraction", color=_dcols[_dn], fontsize=8.5)

    for _ax in (_ax1, _ax2):
        _ax.set_xscale("log"); _ax.grid(alpha=.3, which="both"); _ax.legend()
        _ax.set_xlabel("corpus size N (games)")
    _ax1.set_ylabel("H_T bits/move"); _ax1.set_title("Residual unpredictability H_T vs N")
    _ax2.set_yscale("log"); _ax2.set_ylabel("gzip total bits")
    _ax2.set_title("Description length -- slope=1 means no finite program")

    plt.tight_layout()
    return


@app.cell
def _D_lambda(np):
    _rows = _scaling["combo"]
    _sl, _ = np.polyfit(
        np.log10([r["N"]  for r in _rows]),
        np.log10([r["gz"] for r in _rows]), 1)
    _lam  = 10**(1/_sl) if _sl > 0 else float("nan")
    _desc = ("sub-linear -- Pisot-consistent" if _sl < 0.85
             else "near-linear -- program size grows with corpus")
    return


@app.cell
def _E_header():
    return


@app.cell
def _E_measure(AGENTS, agent_cross_entropy, corpus, np, plt, program_length):
    _eval_c = corpus("combo", n=200, seed=2026)
    _pareto = {}
    for _en, _ef in AGENTS.items():
        _ea = _ef()
        _pareto[_en] = {
            "P": program_length(_ea),
            "H": agent_cross_entropy(_ea, _eval_c),
        }

    _enames = list(_pareto)
    _ePs    = np.array([_pareto[n]["P"] for n in _enames])
    _eHs    = np.array([_pareto[n]["H"] for n in _enames])
    _ecols  = plt.cm.plasma(np.linspace(.15, .85, len(_enames)))

    _fig, _ax = plt.subplots(figsize=(8.5, 5.5))
    _ax.scatter(_ePs, _eHs, s=140, c=_ecols, edgecolor="white", lw=.7, zorder=3)
    for _xi, _yi, _ni in zip(_ePs, _eHs, _enames):
        _ax.annotate(_ni, (_xi, _yi), textcoords="offset points",
                     xytext=(7, 4), fontsize=9)

    _pts = sorted(zip(_ePs, _eHs, _enames))
    _front, _best = [], float("inf")
    for _ex, _ey, _en2 in _pts:
        if _ey < _best:
            _front.append((_ex, _ey)); _best = _ey
    if _front:
        _ax.plot([p[0] for p in _front], [p[1] for p in _front],
                 "--", color="#ff6b6b", alpha=.7, label="Pareto frontier", lw=1.5)

    _ax.set_xlabel("|P| gzipped canonical source (bytes)")
    _ax.set_ylabel("H_T bits/move on combo corpus")
    _ax.set_title("Programme E -- agents as time-bounded models in MDL space")
    _ax.grid(alpha=.3); _ax.legend()
    plt.tight_layout()
    return


@app.cell
def _TR_header():
    return


@app.cell
def _TR_measure(Corpus, MarkovObserver, corpus, math, np, plt, tokens):
    def _per_move(name, n=200):
        _c  = corpus(name, n=n)
        _sp = int(0.8 * len(_c.games))
        _tr = Corpus(_c.games[:_sp], _c.manifest)
        _hd = Corpus(_c.games[_sp:], _c.manifest)
        _obs = MarkovObserver(order=3).fit(tokens(_tr))
        _obs.fit_weights(tokens(_hd))
        _ml  = max((len(g.moves) for g in _hd.games), default=1)
        _su  = np.zeros(_ml); _ct = np.zeros(_ml)
        for _g in _hd.games:
            if not _g.moves: continue
            _q0, _r0 = _g.moves[0]
            _rel = [(_q - _q0, _r - _r0) for _q, _r in _g.moves]
            _ctx: list = []
            for _i, _t in enumerate(_rel):
                _p = _obs.prob(_ctx, _t)
                _su[_i] += -math.log2(max(_p, 1e-12))
                _ct[_i] += 1; _ctx.append(_t)
        return _su / np.maximum(_ct, 1)

    _curves  = {nm: _per_move(nm) for nm in ["random", "greedy", "combo"]}
    _trcols  = {"random": "#666", "greedy": "#1f77b4", "combo": "#d62728"}

    _fig, _ax = plt.subplots(figsize=(9, 4.5))
    for _nm, _y in _curves.items():
        _ax.plot(_y, color=_trcols[_nm], label=_nm, lw=1.5)
    _ax.set_xlabel("move number"); _ax.set_ylabel("mean surprise (bits)")
    _ax.set_title("Time-resolved H_T -- observer surprise through a game")
    _ax.grid(alpha=.3); _ax.legend()
    plt.tight_layout()
    return


@app.cell
def _gr_header():
    return


@app.cell
def _gr_measure(corpus, np, pair_correlation, plt):
    _max_r   = 20
    _grcols  = {"random": "#666", "greedy": "#1f77b4", "combo": "#d62728"}
    _grcurves = {}

    for _nm in _grcols:
        _c   = corpus(_nm, n=200)
        _all = [mv for g in _c.games for mv in g.moves]
        _gr  = pair_correlation(_all, max_r=_max_r)
        _grcurves[_nm] = [_gr.get(r, 0.0) for r in range(1, _max_r + 1)]

    _fig, _ax = plt.subplots(figsize=(9, 4.5))
    _rs = np.arange(1, _max_r + 1)
    for _nm, _y in _grcurves.items():
        _ax.plot(_rs, _y, marker="o", ms=4, color=_grcols[_nm], label=_nm)
    _ax.axhline(1.0, ls="--", color="#aaa", lw=1, label="Poisson baseline")
    _ax.set_xlabel("hex distance r"); _ax.set_ylabel("g(r)")
    _ax.set_title("Pair correlation -- peaks above 1 suggest spatial clustering")
    _ax.grid(alpha=.3); _ax.legend()
    plt.tight_layout()
    return


@app.cell
def _F_header():
    return


@app.cell
def _F_gap(Corpus, MarkovObserver, corpus, np, plt, tokens):
    """Programme F panels 1 & 2 -- Finzi Def. 14 two-observer gap.

    Weak observer T1 = MarkovObserver(order=1).
    Strong observer T2 = MarkovObserver(order=3).

    Def. 14 predicts:
      single-step:  H_T1 - H_T2 = Theta(1)   (bounded, agent-independent)
      k-step:       H_T1 - H_T2 = omega(1)   (grows for structured agents)

    k-step stream: token t+k predicted from context ending at t, so each
    observer must implicitly roll forward k turns.
    """
    def _fit_pair(train_toks, held_toks):
        _t1 = MarkovObserver(order=1).fit(train_toks); _t1.fit_weights(held_toks)
        _t2 = MarkovObserver(order=3).fit(train_toks); _t2.fit_weights(held_toks)
        return _t1, _t2

    def _kstep_stream(cp, k):
        """Emit (ctx, target) pairs where target is k moves ahead of ctx tail."""
        _pairs = []
        for _g in cp.games:
            if len(_g.moves) <= k: continue
            _q0, _r0 = _g.moves[0]
            _rel = [(q-_q0, r-_r0) for q, r in _g.moves]
            for _i in range(len(_rel) - k):
                _pairs.append((_rel[:_i+1], _rel[_i+k]))
        return _pairs

    def _kstep_ce(obs, pairs):
        import math as _math
        _bits, _n = 0.0, 0
        for _ctx, _tgt in pairs:
            _p = obs.prob(_ctx, _tgt)
            _bits += -_math.log2(max(_p, 1e-12))
            _n += 1
        return _bits / max(1, _n)

    _F_agents = ["random", "greedy", "fork_a4", "potgrad", "combo"]
    _F_ks     = [1, 2, 4, 8]
    _F_gap    = {a: [] for a in _F_agents}
    _F_H1     = {a: [] for a in _F_agents}
    _F_H2     = {a: [] for a in _F_agents}

    for _fa in _F_agents:
        _fc   = corpus(_fa, n=200)
        _sp   = int(0.8 * len(_fc.games))
        _ftr  = Corpus(_fc.games[:_sp], _fc.manifest)
        _fhd  = Corpus(_fc.games[_sp:], _fc.manifest)
        _T1, _T2 = _fit_pair(tokens(_ftr), tokens(_fhd))
        for _k in _F_ks:
            _pairs = _kstep_stream(_fhd, _k)
            if not _pairs:
                _F_H1[_fa].append(np.nan); _F_H2[_fa].append(np.nan)
                _F_gap[_fa].append(np.nan); continue
            _h1 = _kstep_ce(_T1, _pairs)
            _h2 = _kstep_ce(_T2, _pairs)
            _F_H1[_fa].append(_h1); _F_H2[_fa].append(_h2)
            _F_gap[_fa].append(_h1 - _h2)

    _Fcols = {"random":"#666","greedy":"#1f77b4","fork_a4":"#ff7f0e",
              "potgrad":"#2ca02c","combo":"#d62728"}

    _fig, (_axL, _axR) = plt.subplots(1, 2, figsize=(13, 4.8))

    _x     = np.arange(len(_F_agents))
    _gap_k1 = [_F_gap[a][0] for a in _F_agents]
    _axL.bar(_x, _gap_k1, color=[_Fcols[a] for a in _F_agents])
    _axL.set_xticks(_x); _axL.set_xticklabels(_F_agents, rotation=12)
    _axL.set_ylabel("H_T1 - H_T2  (bits/move)")
    _axL.set_title("Panel 1 -- single-step gap (predict Theta(1))")
    _axL.grid(alpha=.3, axis="y"); _axL.axhline(0, color="#aaa", lw=.5)

    for _fa in _F_agents:
        _axR.plot(_F_ks, _F_gap[_fa], marker="o", color=_Fcols[_fa], label=_fa, lw=1.5)
    _axR.set_xlabel("lookahead k (turns)")
    _axR.set_ylabel("H_T1 - H_T2  (bits/move)")
    _axR.set_title("Panel 2 -- k-step gap (predict omega(1) for structured)")
    _axR.set_xscale("log"); _axR.set_xticks(_F_ks)
    _axR.get_xaxis().set_major_formatter(plt.matplotlib.ticker.ScalarFormatter())
    _axR.grid(alpha=.3, which="both"); _axR.legend(fontsize=8)

    plt.tight_layout()
    return


@app.cell
def _F_glider(AGENTS, play, plt):
    """Programme F panel 3 -- threat propagation on the Eisenstein lattice.

    A 'glider' in HexGo = a length-2+ chain along one of the 3 axes whose
    centroid translates by a unit vector turn-to-turn. We count, per move,
    how many player-1 chains of length >=3 exist along each axis. The sum
    is the 'propagation load' the weak observer would need to encode.
    """
    from hexgo.game import AXES as _AXES

    def _chain_count(game, player, min_len=3):
        _counts = [0, 0, 0]  # one per axis
        _seen = set()
        for (q, r), p in game.board.items():
            if p != player: continue
            for _ai, (_dq, _dr) in enumerate(_AXES):
                # walk to chain start
                _sq, _sr = q, r
                while game.board.get((_sq - _dq, _sr - _dr)) == player:
                    _sq -= _dq; _sr -= _dr
                _key = (_ai, _sq, _sr)
                if _key in _seen: continue
                _seen.add(_key)
                # walk forward measuring length
                _n = 1; _cq, _cr = _sq, _sr
                while game.board.get((_cq + _dq, _cr + _dr)) == player:
                    _n += 1; _cq += _dq; _cr += _dr
                if _n >= min_len: _counts[_ai] += 1
        return _counts

    _scenarios = [("combo",   "combo"),
                  ("fork_a4", "greedy"),
                  ("random",  "random")]
    _scols = {"combo":"#d62728", "fork_a4":"#ff7f0e", "random":"#666"}

    _fig, _ax = plt.subplots(figsize=(9.5, 4.5))

    for _sa, _sb in _scenarios:
        _g = play(AGENTS[_sa], AGENTS[_sb], max_moves=60, seed=2026)
        # replay move-by-move, counting P1 chains at each step
        from hexgo.game import HexGame as _HG
        _sim = _HG()
        _series = []
        for _p, _mv in zip(_g.player_history, _g.move_history):
            _sim.make(*_mv)
            _c = _chain_count(_sim, 1, min_len=3)
            _series.append(sum(_c))
        _label = f"{_sa} vs {_sb}"
        _ax.plot(range(1, len(_series)+1), _series,
                 marker="o", ms=3, color=_scols[_sa], label=_label, lw=1.4)

    _ax.set_xlabel("move number")
    _ax.set_ylabel("# P1 chains (length >= 3) along any axis")
    _ax.set_title("Panel 3 -- glider load: propagating threats on Z[omega]")
    _ax.grid(alpha=.3); _ax.legend()
    plt.tight_layout()
    return


@app.cell
def _notes():
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
 
    """)
    return


if __name__ == "__main__":
    app.run()
