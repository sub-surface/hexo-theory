"""
Bridge to the hexo game engine.
Adds the hexo project root to sys.path so we can import game.py and elo.py directly.

Resolution order (checked once, first match wins):
  1. HEXO_ROOT env var — set this in any environment where the sibling repo
     isn't a Windows-path sibling of this checkout (Modal containers, CI,
     other machines).
  2. Sibling directory relative to this file (works for the normal main
     checkout).
  3. Hardcoded dev-machine fallback (covers the `.claude/worktrees/*` case,
     where #2 resolves relative to the worktree instead of the real repo).

This one place used to be duplicated as a 3-line "worktree shim" at the top
of every experiments/run_*.py — that's what let the hexgo->hexo rename
silently break ~24 files at once (see CLAUDE.md "Import path"). Everything
now goes through this single resolver instead.
"""
import os
import sys
from pathlib import Path

_DEV_FALLBACK = Path(r"C:\Users\Leon\Desktop\Psychograph\hexo")


def _resolve_hexo_root() -> Path:
    env = os.environ.get("HEXO_ROOT")
    if env:
        return Path(env)
    sibling = Path(__file__).resolve().parent.parent.parent / "hexo"
    if sibling.exists():
        return sibling
    return _DEV_FALLBACK


HEXO_ROOT = _resolve_hexo_root()
if not HEXO_ROOT.exists():
    raise ModuleNotFoundError(
        f"hexo engine not found at {HEXO_ROOT!r}. Set HEXO_ROOT env var, or "
        "check the sibling-repo layout (see CLAUDE.md 'Import path')."
    )
if str(HEXO_ROOT) not in sys.path:
    sys.path.insert(0, str(HEXO_ROOT))

from game import HexGame, AXES, WIN_LENGTH  # noqa: F401
from elo import EisensteinGreedyAgent, RandomAgent  # noqa: F401
from engine.agents import ForkAwareAgent, PotentialGradientAgent, ComboAgent  # noqa: F401
