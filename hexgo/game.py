"""
Bridge to the upstream hexgo game engine.
Adds the hexgo project root to sys.path and re-exports the core objects.
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent / "hexgo"
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from game import HexGame, AXES, WIN_LENGTH, DIRS   # noqa: F401
from elo  import EisensteinGreedyAgent, RandomAgent  # noqa: F401
