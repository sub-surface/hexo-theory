"""Port lab.py cells into the live Modal kernel via code_mode."""
import marimo._code_mode as cm

# Each tuple: (cell-description, source-code)
CELLS = [
    ("viz_controls", '''import marimo as mo

_matchups = {
    "combo vs greedy":   ("combo",   "greedy"),
    "combo vs combo":    ("combo",   "combo"),
    "potgrad vs greedy": ("potgrad", "greedy"),
    "fork_a4 vs greedy": ("fork_a4", "greedy"),
    "random vs random":  ("random",  "random"),
}
matchups = _matchups
dd   = mo.ui.dropdown(list(_matchups), value="combo vs greedy", label="matchup")
nmv  = mo.ui.slider(4, 80, value=32, label="moves")
seed = mo.ui.number(0, 9999, value=2026, label="seed")
btn  = mo.ui.run_button(label="play")
pot  = mo.ui.checkbox(True, label="potential heatmap")
thr  = mo.ui.checkbox(True, label="threats")
frk  = mo.ui.checkbox(True, label="forks")
mo.hstack([dd, nmv, seed, pot, thr, frk, btn], gap="1rem")
'''),
    ("viz_board", '''_a, _b = matchups[dd.value]
_g = play(AGENTS[_a], AGENTS[_b], max_moves=nmv.value, seed=seed.value)
_fig, _ax = plt.subplots(figsize=(7, 6.3))
draw_board(_g, _ax,
           show_potential=pot.value,
           show_threats=thr.value,
           show_forks=frk.value,
           title=f"{_a} vs {_b}  |  "
                 f"{'P'+str(_g.winner)+' wins' if _g.winner else 'ongoing'}  |  "
                 f"{len(_g.move_history)} moves")
plt.tight_layout()
_fig
'''),
    ("A_measure", '''A_results = {}
for _nm in ["random", "greedy", "fork_a4", "potgrad", "combo"]:
    _c = corpus(_nm, n=200)
    _r = measure(_c, name=_nm)
    A_results[_nm] = {
        "H_markov": _r.markov_H,
        "H_gzip":   _r.gzip_H,
        "S_markov": _r.markov_S,
        "prog":     program_length(AGENTS[_nm]()),
    }

_names  = list(A_results)
_Hm     = [A_results[n]["H_markov"] for n in _names]
_Hgz    = [A_results[n]["H_gzip"]   for n in _names]
_cols   = ["#666", "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]
_x      = np.arange(len(_names))

_fig, (_ax1, _ax2) = plt.subplots(1, 2, figsize=(13, 4.8))

_ax1.bar(_x - .18, _Hm,  .36, label="Markov-3", color=_cols)
_ax1.bar(_x + .18, _Hgz, .36, label="gzip",     color=_cols, alpha=.5, hatch="//")
_ax1.set_xticks(_x); _ax1.set_xticklabels(_names, rotation=12)
_ax1.set_ylabel("bits / move")
_ax1.set_title("Cross-entropy H_T by agent corpus")
_ax1.grid(alpha=.3, axis="y"); _ax1.legend()

_Ps = [A_results[n]["prog"] for n in _names]
_ax2.scatter(_Ps, _Hm, s=120, c=_cols, edgecolor="white", lw=.7, zorder=3)
for _xi, _yi, _ni in zip(_Ps, _Hm, _names):
    _ax2.annotate(_ni, (_xi, _yi), textcoords="offset points",
                  xytext=(6, 4), fontsize=9)
_ax2.set_xlabel("|P| gzipped source (bytes)")
_ax2.set_ylabel("H_T (bits/move)")
_ax2.set_title("Programme A snapshot in MDL space")
_ax2.grid(alpha=.3)

plt.tight_layout()
_fig
'''),
    ("D_measure", '''D_sizes   = [50, 100, 200, 500, 1000]
D_scaling = {"random": [], "greedy": [], "combo": []}

for _dn in D_scaling:
    for _ds in D_sizes:
        _dc = corpus(_dn, n=_ds, seed=7)
        _dr = measure(_dc, name=_dn)
        D_scaling[_dn].append({"N": _ds, "H": _dr.markov_H, "gz": _dr.gzip_total})

_dcols = {"random": "#666", "greedy": "#1f77b4", "combo": "#d62728"}
_dmks  = {"random": "o",    "greedy": "s",       "combo": "^"}

_fig, (_ax1, _ax2) = plt.subplots(1, 2, figsize=(13, 4.8))

for _dn, _rows in D_scaling.items():
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
            xy=(.03, .92 - .09 * list(D_scaling).index(_dn)),
            xycoords="axes fraction", color=_dcols[_dn], fontsize=8.5)

for _ax in (_ax1, _ax2):
    _ax.set_xscale("log"); _ax.grid(alpha=.3, which="both"); _ax.legend()
    _ax.set_xlabel("corpus size N (games)")
_ax1.set_ylabel("H_T bits/move"); _ax1.set_title("Residual unpredictability H_T vs N")
_ax2.set_yscale("log"); _ax2.set_ylabel("gzip total bits")
_ax2.set_title("Description length -- slope=1 means no finite program")

plt.tight_layout()
_fig
'''),
    ("E_measure", '''_eval_c = corpus("combo", n=200, seed=2026)
E_pareto = {}
for _en, _ef in AGENTS.items():
    _ea = _ef()
    E_pareto[_en] = {
        "P": program_length(_ea),
        "H": agent_cross_entropy(_ea, _eval_c),
    }

_enames = list(E_pareto)
_ePs    = np.array([E_pareto[n]["P"] for n in _enames])
_eHs    = np.array([E_pareto[n]["H"] for n in _enames])
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
_fig
'''),
    ("TR_measure", '''def per_move(name, n=200):
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

TR_curves  = {nm: per_move(nm) for nm in ["random", "greedy", "combo"]}
_trcols  = {"random": "#666", "greedy": "#1f77b4", "combo": "#d62728"}

_fig, _ax = plt.subplots(figsize=(9, 4.5))
for _nm, _y in TR_curves.items():
    _ax.plot(_y, color=_trcols[_nm], label=_nm, lw=1.5)
_ax.set_xlabel("move number"); _ax.set_ylabel("mean surprise (bits)")
_ax.set_title("Time-resolved H_T -- observer surprise through a game")
_ax.grid(alpha=.3); _ax.legend()
plt.tight_layout()
_fig
'''),
    ("gr_measure", '''_max_r   = 20
_grcols  = {"random": "#666", "greedy": "#1f77b4", "combo": "#d62728"}
grcurves = {}

for _nm in _grcols:
    _c   = corpus(_nm, n=200)
    _all = [mv for g in _c.games for mv in g.moves]
    _gr  = pair_correlation(_all, max_r=_max_r)
    grcurves[_nm] = [_gr.get(r, 0.0) for r in range(1, _max_r + 1)]

_fig, _ax = plt.subplots(figsize=(9, 4.5))
_rs = np.arange(1, _max_r + 1)
for _nm, _y in grcurves.items():
    _ax.plot(_rs, _y, marker="o", ms=4, color=_grcols[_nm], label=_nm)
_ax.axhline(1.0, ls="--", color="#aaa", lw=1, label="Poisson baseline")
_ax.set_xlabel("hex distance r"); _ax.set_ylabel("g(r)")
_ax.set_title("Pair correlation -- peaks above 1 suggest spatial clustering")
_ax.grid(alpha=.3); _ax.legend()
plt.tight_layout()
_fig
'''),
]


async def main():
    async with cm.get_context(skip_validation=True) as ctx:
        existing = list(ctx.cells.keys())
        print("existing cells:", existing)
        new_ids = []
        for desc, code in CELLS:
            cid = ctx.create_cell(code)
            new_ids.append((desc, cid))
            print(f"created {desc} -> {cid}")
        print("\nnew cell ids:", new_ids)

import asyncio
asyncio.get_event_loop().run_until_complete(main())
