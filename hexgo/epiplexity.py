"""
Epiplexity — time-bounded two-part MDL measurements.

Finzi et al. 2026, Def. 8:
  MDL_T(X) = S_T(X) + H_T(X)
           = |P*|   + E[log 1/P*(X)]

Two torch-free observers:
  MarkovObserver  — mixed-order back-off LM; |P| = gzipped table size
  gzip_bits       — practical universal compressor (Kolmogorov upper bound)

Corpus generation, serialisation, and agent-as-model cross-entropy live here.
"""
from __future__ import annotations
import ast, gzip, inspect, math, pickle, random
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

from hexgo.game import HexGame


# ── agent description length ─────────────────────────────────────────────────

def program_length(agent) -> int:
    """Gzipped canonical-source bytes of the agent class — proxy for |P|."""
    cls = agent if isinstance(agent, type) else type(agent)
    try:
        src = inspect.getsource(cls)
        tree = ast.parse(src)
        # strip top-level docstrings to reduce stylistic noise
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Module)):
                if (node.body and isinstance(node.body[0], ast.Expr)
                        and isinstance(node.body[0].value, ast.Constant)):
                    node.body = node.body[1:] or [ast.Pass()]
        raw = ast.unparse(tree).encode()
    except Exception:
        raw = repr(cls).encode()
    return len(gzip.compress(raw, mtime=0, compresslevel=9))


# ── corpus ───────────────────────────────────────────────────────────────────

@dataclass
class Game:
    moves:   list[tuple[int, int]]
    players: list[int]
    winner:  int | None

    @classmethod
    def from_hexgame(cls, g: HexGame) -> "Game":
        return cls(list(g.move_history), list(g.player_history), g.winner)


@dataclass
class Corpus:
    games:    list[Game]
    manifest: dict[str, Any] = field(default_factory=dict)

    def save(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(path, "wb") as f:
            pickle.dump({"games": self.games, "manifest": self.manifest}, f)

    @classmethod
    def load(cls, path: Path) -> "Corpus":
        with gzip.open(path, "rb") as f:
            d = pickle.load(f)
        return cls(d["games"], d["manifest"])

    def __len__(self): return len(self.games)
    def __iter__(self): return iter(self.games)


def generate(factory_a: Callable, factory_b: Callable,
             n: int, seed: int = 0, max_moves: int = 150) -> Corpus:
    """Self-play corpus: n games, alternating sides."""
    rng = random.Random(seed)
    games = []
    for i in range(n):
        random.seed(rng.randint(0, 2**31-1))
        a, b = factory_a(), factory_b()
        if i % 2 == 1: a, b = b, a
        g = HexGame()
        m = 0
        while g.winner is None and m < max_moves:
            ag = a if g.current_player == 1 else b
            legal = g.legal_moves()
            if not legal: break
            mv = ag.choose_move(g)
            if mv not in set(legal): mv = rng.choice(legal)
            g.make(*mv); m += 1
        games.append(Game.from_hexgame(g))
    return Corpus(games, {"agent_a": factory_a().__class__.__name__,
                          "agent_b": factory_b().__class__.__name__,
                          "n": n, "seed": seed})


# ── tokenisation ─────────────────────────────────────────────────────────────

def tokens(corpus: Corpus) -> list:
    """Relative-coord move tokens, None as game separator."""
    out = []
    for g in corpus.games:
        if not g.moves: continue
        q0, r0 = g.moves[0]
        out.extend((q-q0, r-r0) for q, r in g.moves)
        out.append(None)
    return out


# ── Markov back-off observer ──────────────────────────────────────────────────

class MarkovObserver:
    """Order-n back-off language model over move tokens.

    H_T  = held-out cross-entropy (bits/token)
    |P|  = gzipped pickle of transition tables (bits)
    """

    def __init__(self, order: int = 3, smooth: float = 0.1):
        self.order, self.smooth = order, smooth
        self.counts: list[dict] = [defaultdict(Counter) for _ in range(order+1)]
        self.vocab:  set = set()
        self.weights: list[float] = []

    # ── fitting ──

    def fit(self, stream: Sequence) -> "MarkovObserver":
        self.vocab = {t for t in stream if t is not None}
        for k in range(self.order+1):
            self.counts[k] = defaultdict(Counter)
        for t in range(len(stream)):
            if stream[t] is None: continue
            for k in range(self.order+1):
                if t < k: continue
                ctx = tuple(stream[t-k:t])
                if None in ctx: continue
                self.counts[k][ctx][stream[t]] += 1
        self.weights = [1/(self.order+1)] * (self.order+1)
        return self

    def fit_weights(self, held: Sequence, grid: int = 5):
        """Grid search over simplex of interpolation weights."""
        best = (float("inf"), self.weights[:])
        def _simplex(rem, left):
            if left == 1: yield [rem]; return
            for i in range(grid+1):
                v = i/grid
                if v > rem+1e-9: break
                for tail in _simplex(rem-v, left-1): yield [v]+tail
        for ws in _simplex(1.0, self.order+1):
            self.weights = ws
            ce = self.cross_entropy(held)
            if ce < best[0]: best = (ce, ws[:])
        self.weights = best[1]

    # ── inference ──

    def _pk(self, k, ctx, x):
        tbl = self.counts[k].get(ctx)
        V = max(1, len(self.vocab))
        if not tbl: return 1/V
        tot = sum(tbl.values())
        return (tbl.get(x, 0) + self.smooth) / (tot + self.smooth*V)

    def prob(self, ctx, x) -> float:
        p = 0.0
        for k in range(self.order+1):
            c = () if k == 0 else tuple(ctx[-k:])
            if None in c: c = ()
            p += self.weights[k] * self._pk(k, c, x)
        return max(p, 1e-12)

    def cross_entropy(self, stream: Sequence) -> float:
        bits, n, ctx = 0.0, 0, []
        for t in stream:
            if t is None: ctx = []; continue
            bits += -math.log2(self.prob(ctx, t))
            ctx.append(t); n += 1
        return bits / max(1, n)

    def program_length(self) -> int:
        """Gzipped table size in bits — proxy for S_T."""
        payload = {"order": self.order, "smooth": self.smooth,
                   "vocab": len(self.vocab),
                   "counts": [{str(k): dict(v) for k,v in c.items()}
                               for c in self.counts],
                   "weights": self.weights}
        return 8 * len(gzip.compress(pickle.dumps(payload), mtime=0, compresslevel=9))


# ── gzip observer ─────────────────────────────────────────────────────────────

def gzip_bits(corpus: Corpus) -> tuple[float, int]:
    """(bits_per_token, total_bits) via gzip on the token stream."""
    buf, n = bytearray(), 0
    for t in tokens(corpus):
        if t is None: buf += bytes([0xFF, 0xFF]); continue
        dq, dr = t
        buf.append(((dq<<1)^(dq>>31)) & 0xFF)
        buf.append(((dr<<1)^(dr>>31)) & 0xFF)
        n += 1
    total = 8 * len(gzip.compress(bytes(buf), mtime=0, compresslevel=9))
    return total/max(1,n), total


# ── MDL report ────────────────────────────────────────────────────────────────

@dataclass
class MDLResult:
    name:        str
    n_games:     int
    n_tokens:    int
    markov_H:    float   # bits/token
    markov_S:    int     # bits (program length)
    gzip_H:      float   # bits/token
    gzip_total:  int     # bits

    def mdl(self) -> float:
        return self.markov_S + self.n_tokens * self.markov_H


def measure(corpus: Corpus, name: str = "", holdout: float = 0.2,
            order: int = 3) -> MDLResult:
    """Fit observers, return MDL measurements."""
    toks = tokens(corpus)
    split = int(len(toks)*(1-holdout))
    while split < len(toks) and toks[split] is not None: split += 1
    train, test = toks[:split], toks[split:]

    obs = MarkovObserver(order).fit(train)
    obs.fit_weights(test)
    H = obs.cross_entropy(test)
    S = obs.program_length()
    n = sum(1 for t in toks if t is not None)
    gz_H, gz_total = gzip_bits(corpus)
    return MDLResult(name or corpus.manifest.get("agent_a","?"),
                     len(corpus.games), n, H, S, gz_H, gz_total)


# ── agent-as-model cross-entropy ──────────────────────────────────────────────

def agent_cross_entropy(agent, corpus: Corpus) -> float:
    """Bits/move: how surprised the agent is by each move in the corpus.

    Agent is modelled as deterministic with ε-uniform smoothing.
    """
    eps = 0.02
    bits, n = 0.0, 0
    for game in corpus.games:
        g = HexGame()
        for mv in game.moves:
            legal = g.legal_moves()
            if not legal or mv not in set(legal): break
            dist_mv = agent.choose_move(g)
            p = (1-eps) if mv == dist_mv else eps/max(1, len(legal)-1)
            bits += -math.log2(max(p, 1e-12))
            n += 1
            g.make(*mv)
    return bits / max(1, n)
