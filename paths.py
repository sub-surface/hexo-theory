"""Canonical repository paths for hexo-theory.

Keep filesystem layout decisions here so experiments and apps do not grow
their own ideas about where evidence, source bundles, or generated files live.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent

APPS = ROOT / "apps"
CLOUD = ROOT / "cloud"
EVIDENCE = ROOT / "evidence"
SOURCES = ROOT / "sources"

RESULTS = EVIDENCE / "results"
FIGURES = EVIDENCE / "figures"
CORPORA = EVIDENCE / "corpora"
GAMES = EVIDENCE / "games"

LITERATURE = SOURCES / "literature"
BUNDLES = SOURCES / "bundles"
EXTERNAL_RUNS = SOURCES / "external-runs"


def ensure_evidence_dirs() -> None:
    """Create writable evidence directories used by experiments."""
    for path in (RESULTS, FIGURES, CORPORA, GAMES):
        path.mkdir(parents=True, exist_ok=True)
