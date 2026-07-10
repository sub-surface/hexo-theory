"""
Shared Modal image factory for anything that needs the compiled hexgo-rs
Rust extension (and optionally the vendored SealBot port).

This existed as copy-pasted image recipes in modal_app.py, modal_rust_bot.py,
and (about to be) modal_bakeoff.py -- three near-identical Dockerfile-shaped
blocks that could silently drift. Factored out 2026-07-08 as part of the
Python/Rust workflow cleanup (see competition/2026-07-08-optimal-play-and-
bot-design.md section 4): the goal is ONE bake-off tool (modal_bakeoff.py,
via competition/external_bots.py's adapters) instead of a growing pile of
bespoke per-opponent Modal scripts, and this is the shared image half of
that. modal_app.py / modal_theory_sweep.py still carry their own copies as
of this writing -- not yet migrated, left for a follow-up pass, not because
the duplication there is fine.

Import and call `hexo_rust_image(...)` from any Modal app module; each
caller still needs its own `modal.App(...)` and `@app.function(image=...)`.
"""
from __future__ import annotations

from pathlib import Path

import modal

THEORY_ROOT = Path(__file__).resolve().parents[2]
HEXO_ROOT = THEORY_ROOT.parent / "hexo"
RAMORA_ROOT = THEORY_ROOT / "sources" / "external-runs" / "misc" / "hexbot-building-framework" / "opponents"


def hexo_rust_image(include_ramora: bool = False) -> modal.Image:
    """Debian slim + Python 3.12 + a from-source build of hexgo-rs's PyO3
    extension. Building fresh on Linux with an explicit python_version
    sidesteps the Windows py-launcher confusion that made local `maturin
    develop` target the wrong CPython no matter how it was invoked (see
    modal_rust_bot.py's original docstring for the full story) -- this is
    the ONLY reliably-working way to test the PyO3 binding for this repo.

    include_ramora=True additionally vendors the SealBot port (sources/external-runs/misc/
    hexbot-building-framework/opponents/ramora) so opponents.ramora.ai.
    MinimaxBot is importable -- pure stdlib, no orca/torch dependency chain
    comes along (see competition/external_bots.py's make_sealbot).
    """
    img = (
        modal.Image.debian_slim(python_version="3.12")
        .apt_install("curl", "build-essential")
        .run_commands("curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y")
        .pip_install("maturin", "numpy")
        .add_local_dir(str(HEXO_ROOT / "hexgo-rs"), "/root/hexgo-rs", copy=True,
                        ignore=["target", ".git"])
        .run_commands(". /root/.cargo/env && cd /root/hexgo-rs && maturin build --release"
                      " && pip install target/wheels/*.whl")
    )
    if include_ramora:
        img = img.add_local_dir(str(RAMORA_ROOT), "/root/opponents", copy=True,
                                ignore=["__pycache__", ".git"])
    return img
