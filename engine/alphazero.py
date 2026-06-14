"""UnifiedTrunk + heads for the Phase 0 / Phase 1 / Phase 2 agent.

Architecture, per `docs/theory/2026-04-18-unified-agent-design.md`:

    UnifiedTrunk       6-layer HexConv stack, hidden=32
      |
      +--- policy head       (B, 1, H, W)   next-move logits
      +--- value head        (B, 1)         scalar in [-1, +1] (tanh)
      +--- threat head       (B, 2, H, W)   per-cell {threat_self, threat_opp}
      +--- win-cell head     (B, 1, H, W)   per-cell winning-move probability
      +--- (optional) fork/potential heads

Parameter budget sanity check, hidden=32, depth=6:
    first layer: 4 -> 32          = 32 * (4*3) + 32         = 416
    5 layers 32->32:              = (32*(32*3)+32) * 5      = 15520
    policy 32->1 (3x3 hex):       = 1 * (32*3) + 1          = 97
    value attn + linear:          = 97 + 33                 = 130
    threat 32->2:                 = 194
    win 32->1:                    = 97
    fork 32->1:                   = 97
    potential 32->1:              = 97
    TOTAL ~= 16.7k              (well within 5GB VRAM on the 2060)

The trunk is structurally the same as `observer.StrategyTrunk` but with
hidden=32 + depth=6 (vs 16/4 default), and exposes the feature map
directly for multiple heads.

Phase 0 (this file, along with run_az_pretrain.py):
    - pretrain the trunk on static_positions data with:
        L_total = L_policy + lambda_t * L_threat
                        + lambda_w * L_win + lambda_f * L_fork
                        + lambda_p * L_potential  + lambda_v * L_value
    - no self-play needed; just regress on cached npz files.

Phase 2a (MC value, landing 2026-04-19):
    - value target = Monte-Carlo λ=1 return: rec["value"] ∈ {-1, 0, +1}
      from the to-move player's perspective (backfilled from final game
      outcome). ~42% of samples have non-zero target; the 58% of
      mid-game positions with value=0 are legitimate ties vs
      uninformative-ignore -- we regress on all of them and let MSE
      shrink predictions toward 0 in uncertain positions.
    - this is the λ=1 limit of TD(λ): no bootstrapping, just the
      final return. The cheapest valid test of whether the value head
      can learn anything useful before we invest in self-play TD.

Phase 2b+ (MCTS + TD(λ) self-play, TBD):
    - value head trained via MCTS-bootstrapped TD target (λ<1)
    - policy head distilled against MCTS visit counts
    - auxiliary heads stay active as regularisers

Key design choices:
    * NO inference-mode toggle calls anywhere in the public API --
      we use `trunk.train(False)` plus `requires_grad_(False)` when
      freezing (matches the pattern in `engine/observer.py`).
    * Value head uses attention-weighted pool over cells (not mean)
      so empty regions don't wash out the signal.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from engine.neural_ca import HexConv2d


# -- Architecture --------------------------------------------------------------


class UnifiedTrunk(nn.Module):
    """HexConv stack producing a per-cell feature map."""

    def __init__(self, in_ch: int = 4, hidden: int = 32, depth: int = 6):
        super().__init__()
        layers: list[nn.Module] = []
        c = in_ch
        for _ in range(depth):
            layers.append(HexConv2d(c, hidden))
            layers.append(nn.ReLU(inplace=True))
            c = hidden
        self.net = nn.Sequential(*layers)
        self.hidden = hidden
        self.depth = depth

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class PolicyHead(nn.Module):
    def __init__(self, hidden: int):
        super().__init__()
        self.head = HexConv2d(hidden, 1)

    def forward(self, feats: torch.Tensor) -> torch.Tensor:
        return self.head(feats).squeeze(1)


class ThreatHead(nn.Module):
    """Per-cell logits for {threat_self, threat_opp}. Independent sigmoids."""

    def __init__(self, hidden: int):
        super().__init__()
        self.head = HexConv2d(hidden, 2)

    def forward(self, feats: torch.Tensor) -> torch.Tensor:
        return self.head(feats)  # (B, 2, H, W)


class WinCellHead(nn.Module):
    def __init__(self, hidden: int):
        super().__init__()
        self.head = HexConv2d(hidden, 1)

    def forward(self, feats: torch.Tensor) -> torch.Tensor:
        return self.head(feats).squeeze(1)


class ForkHead(nn.Module):
    def __init__(self, hidden: int):
        super().__init__()
        self.head = HexConv2d(hidden, 1)

    def forward(self, feats: torch.Tensor) -> torch.Tensor:
        return self.head(feats).squeeze(1)


class PotentialHead(nn.Module):
    def __init__(self, hidden: int):
        super().__init__()
        self.head = HexConv2d(hidden, 1)

    def forward(self, feats: torch.Tensor) -> torch.Tensor:
        return self.head(feats).squeeze(1)


class ValueHead(nn.Module):
    """Attention-pooled scalar value, output in [-1, 1] via tanh."""

    def __init__(self, hidden: int):
        super().__init__()
        self.attn = HexConv2d(hidden, 1)
        self.value = nn.Linear(hidden, 1)

    def forward(self, feats: torch.Tensor) -> torch.Tensor:
        B, C, H, W = feats.shape
        attn = self.attn(feats).view(B, -1)
        attn = F.softmax(attn, dim=1).view(B, 1, H, W)
        pooled = (feats * attn).sum(dim=(2, 3))
        return torch.tanh(self.value(pooled)).squeeze(-1)


class UnifiedNet(nn.Module):
    """UnifiedTrunk + all six heads. Forward returns a dict."""

    def __init__(self, hidden: int = 32, depth: int = 6):
        super().__init__()
        self.trunk = UnifiedTrunk(in_ch=4, hidden=hidden, depth=depth)
        self.policy = PolicyHead(hidden)
        self.value = ValueHead(hidden)
        self.threat = ThreatHead(hidden)
        self.win = WinCellHead(hidden)
        self.fork = ForkHead(hidden)
        self.potential = PotentialHead(hidden)
        self.hidden = hidden
        self.depth = depth

    def forward(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        f = self.trunk(x)
        return {
            "policy": self.policy(f),
            "value": self.value(f),
            "threat": self.threat(f),
            "win": self.win(f),
            "fork": self.fork(f),
            "potential": self.potential(f),
        }


# -- Static-position dataset loader -------------------------------------------


@dataclass
class PositionSample:
    arr: np.ndarray
    labels: np.ndarray
    policy: np.ndarray
    value: float
    to_move: int


class StaticPositionDataset:
    """Loads from data/static_positions/{train,val}_*.npz."""

    def __init__(self, dir_path: str, split: str = "train", max_samples: int | None = None):
        from pathlib import Path
        p = Path(dir_path)
        files = sorted(p.glob(f"{split}_*.npz"))
        if max_samples:
            files = files[:max_samples]
        self.files = files

    def __len__(self) -> int:
        return len(self.files)

    def __getitem__(self, i: int) -> PositionSample:
        d = np.load(self.files[i])
        return PositionSample(
            arr=d["arr"],
            labels=d["labels"],
            policy=d["policy"],
            value=float(d["value"]),
            to_move=int(d["to_move"]),
        )


def pad_to(arr: np.ndarray, H: int, W: int) -> np.ndarray:
    """Zero-pad (C,h,w) -> (C,H,W) with channel 0 = empty restored."""
    C, h, w = arr.shape
    if h == H and w == W:
        return arr
    out = np.zeros((C, H, W), dtype=arr.dtype)
    out[0] = 1.0
    out[:, :h, :w] = arr
    if C >= 4:
        out[3] = arr[3, 0, 0]
    return out


def pad_label(arr: np.ndarray, H: int, W: int) -> np.ndarray:
    C, h, w = arr.shape
    if h == H and w == W:
        return arr
    out = np.zeros((C, H, W), dtype=arr.dtype)
    out[:, :h, :w] = arr
    return out


def pad_2d(arr: np.ndarray, H: int, W: int) -> np.ndarray:
    h, w = arr.shape
    if h == H and w == W:
        return arr
    out = np.zeros((H, W), dtype=arr.dtype)
    out[:h, :w] = arr
    return out


def collate(samples: list[PositionSample], device: str = "cuda") -> dict:
    H = max(s.arr.shape[1] for s in samples)
    W = max(s.arr.shape[2] for s in samples)
    B = len(samples)
    arrs = np.stack([pad_to(s.arr, H, W) for s in samples])
    labels = np.stack([pad_label(s.labels, H, W) for s in samples])
    policies = np.stack([pad_2d(s.policy, H, W) for s in samples])
    values = np.array([s.value for s in samples], dtype=np.float32)
    flat = np.full(B, -1, dtype=np.int64)
    for i, p in enumerate(policies):
        idx = int(np.argmax(p))
        if p.flat[idx] > 0.5:
            flat[i] = idx
    return {
        "x": torch.from_numpy(arrs).to(device),
        "labels": torch.from_numpy(labels).to(device),
        "policy": torch.from_numpy(policies).to(device),
        "policy_flat": torch.from_numpy(flat).to(device),
        "value": torch.from_numpy(values).to(device),
        "H": H, "W": W,
    }


# -- Phase 0 supervised pretrain ----------------------------------------------


def pretrain_trunk(
    dataset_dir: str,
    *,
    hidden: int = 32,
    depth: int = 6,
    epochs: int = 40,
    batch_size: int = 32,
    lr: float = 3e-4,
    lambda_threat: float = 1.0,
    lambda_win: float = 1.0,
    lambda_fork: float = 0.3,
    lambda_pot: float = 0.3,
    lambda_policy: float = 1.0,
    lambda_value: float = 1.0,
    mask_zero_value: bool = False,
    device: str = "cuda",
    seed: int = 42,
    val_every: int = 2,
    max_train: int | None = None,
) -> tuple[UnifiedNet, dict]:
    """Supervised trunk pretrain.

    Trains policy + threat + win + fork + potential + value heads on
    labels from engine.analysis. Value target is the Monte-Carlo λ=1
    return stored in rec["value"] by gen_static_positions.py (+1 if the
    to-move player ends up winning, -1 if losing, 0 for draws or
    unresolved games). ~42% of samples have |value|=1.

    Returns (model, history) with per-epoch train/val losses + accuracy.
    """
    torch.manual_seed(seed)
    np.random.seed(seed)

    train_ds = StaticPositionDataset(dataset_dir, "train", max_samples=max_train)
    val_ds = StaticPositionDataset(dataset_dir, "val")
    assert len(train_ds) > 0, f"no training data in {dataset_dir}"
    assert len(val_ds) > 0, f"no val data in {dataset_dir}"

    # Pre-compute (H, W) per sample by peeking at each npz header. Sorting
    # samples by HxW and taking sequential batches avoids pad-to-max memory
    # blow-ups when grid sizes range from 9x9 to 45x39 on the infinite lattice.
    def _shape_keys(ds: StaticPositionDataset) -> np.ndarray:
        keys = np.zeros(len(ds), dtype=np.int64)
        for i, f in enumerate(ds.files):
            with np.load(f) as d:
                keys[i] = int(d["arr"].shape[1]) * int(d["arr"].shape[2])
        return keys
    train_keys = _shape_keys(train_ds)
    val_keys = _shape_keys(val_ds)

    model = UnifiedNet(hidden=hidden, depth=depth).to(device)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"UnifiedNet: hidden={hidden} depth={depth} params={n_params:,}")
    print(f"  train grid HxW: min={train_keys.min()} median={int(np.median(train_keys))} max={train_keys.max()}")

    opt = torch.optim.Adam(model.parameters(), lr=lr)

    history = {
        "epoch": [], "train_loss": [], "val_loss": [],
        "train_policy_acc": [], "val_policy_acc": [],
        "train_threat_f1": [], "val_threat_f1": [],
        "train_win_f1": [], "val_win_f1": [],
        "train_value_mse": [], "val_value_mse": [],
        "train_value_sign_acc": [], "val_value_sign_acc": [],
    }

    def _run_split(ds: StaticPositionDataset, train: bool, keys: np.ndarray) -> dict:
        model.train(train)
        # Sort by HxW so each batch has homogeneous grid sizes (no padding blow-up).
        order = np.argsort(keys, kind="stable")
        if train:
            # Chunk the sorted order into batches, shuffle the *batches* only.
            n_batches_pre = max(1, (len(order) + batch_size - 1) // batch_size)
            chunks = [order[b * batch_size:(b + 1) * batch_size] for b in range(n_batches_pre)]
            np.random.shuffle(chunks)
            idxs = np.concatenate(chunks) if chunks else order
        else:
            idxs = order
        n_batches = max(1, (len(ds) + batch_size - 1) // batch_size)
        totals = {
            "loss": 0.0, "policy": 0.0, "threat": 0.0, "win": 0.0,
            "fork": 0.0, "pot": 0.0, "value": 0.0,
            "policy_correct": 0, "policy_total": 0,
            "threat_tp": 0, "threat_fp": 0, "threat_fn": 0,
            "win_tp": 0, "win_fp": 0, "win_fn": 0,
            "value_sq_err": 0.0, "value_n": 0,
            "value_sign_correct": 0, "value_sign_total": 0,
        }
        def _batch_step(c: dict) -> None:
            x = c["x"]
            labels = c["labels"]
            policy_t = c["policy_flat"]
            B = x.shape[0]
            if train:
                opt.zero_grad(set_to_none=True)
            out = model(x)

            logits_p = out["policy"].reshape(B, -1)
            valid = policy_t >= 0
            if valid.any():
                loss_policy = F.cross_entropy(
                    logits_p[valid], policy_t[valid], reduction="mean"
                )
                preds = logits_p[valid].argmax(dim=1)
                totals["policy_correct"] += int((preds == policy_t[valid]).sum().item())
                totals["policy_total"] += int(valid.sum().item())
            else:
                loss_policy = torch.zeros((), device=device)

            threat_logits = out["threat"]
            threat_target = labels[:, 0:2]
            loss_threat = F.binary_cross_entropy_with_logits(
                threat_logits, threat_target, reduction="mean"
            )
            win_logits = out["win"]
            win_target = labels[:, 4]
            loss_win = F.binary_cross_entropy_with_logits(
                win_logits, win_target, reduction="mean"
            )
            fork_logits = out["fork"]
            fork_target = labels[:, 2]
            loss_fork = F.binary_cross_entropy_with_logits(
                fork_logits, fork_target, reduction="mean"
            )
            pot_logits = out["potential"]
            pot_target = labels[:, 3]
            loss_pot = F.mse_loss(torch.sigmoid(pot_logits), pot_target)

            value_pred = out["value"]
            value_target = c["value"]
            # MSE on tanh output vs {-1, 0, +1} target. Both in [-1, 1].
            # Optionally mask out v=0 samples -- 58% of the corpus has
            # value=0 (unresolved mid-game positions) and regressing on
            # them teaches the head to always predict 0. See design §13.2.
            if mask_zero_value:
                nonzero = value_target.abs() > 0.5
                if nonzero.any():
                    loss_value = F.mse_loss(value_pred[nonzero], value_target[nonzero])
                else:
                    loss_value = torch.zeros((), device=device)
            else:
                loss_value = F.mse_loss(value_pred, value_target)

            loss = (lambda_policy * loss_policy
                    + lambda_threat * loss_threat
                    + lambda_win * loss_win
                    + lambda_fork * loss_fork
                    + lambda_pot * loss_pot
                    + lambda_value * loss_value)

            if train:
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                opt.step()

            totals["loss"] += float(loss.detach().cpu()) * B
            totals["policy"] += float(loss_policy.detach().cpu()) * B
            totals["threat"] += float(loss_threat.detach().cpu()) * B
            totals["win"] += float(loss_win.detach().cpu()) * B
            totals["fork"] += float(loss_fork.detach().cpu()) * B
            totals["pot"] += float(loss_pot.detach().cpu()) * B
            totals["value"] += float(loss_value.detach().cpu()) * B

            # Value probes: per-sample MSE, and sign accuracy on |target|=1.
            vp = value_pred.detach()
            vt = value_target.detach()
            totals["value_sq_err"] += float(((vp - vt) ** 2).sum().cpu())
            totals["value_n"] += int(B)
            decisive = vt.abs() > 0.5
            if decisive.any():
                sign_correct = (vp[decisive].sign() == vt[decisive].sign()).sum()
                totals["value_sign_correct"] += int(sign_correct.cpu())
                totals["value_sign_total"] += int(decisive.sum().cpu())

            # Detach the probes so we don't retain the graph.
            t_pred = (torch.sigmoid(threat_logits.detach()) > 0.5).float()
            totals["threat_tp"] += int(((t_pred == 1) & (threat_target == 1)).sum().item())
            totals["threat_fp"] += int(((t_pred == 1) & (threat_target == 0)).sum().item())
            totals["threat_fn"] += int(((t_pred == 0) & (threat_target == 1)).sum().item())
            w_pred = (torch.sigmoid(win_logits.detach()) > 0.5).float()
            totals["win_tp"] += int(((w_pred == 1) & (win_target == 1)).sum().item())
            totals["win_fp"] += int(((w_pred == 1) & (win_target == 0)).sum().item())
            totals["win_fn"] += int(((w_pred == 0) & (win_target == 1)).sum().item())

        for b in range(n_batches):
            batch_idx = idxs[b * batch_size:(b + 1) * batch_size]
            batch = [ds[int(i)] for i in batch_idx]
            if not batch:
                continue
            c = collate(batch, device=device)
            if train:
                _batch_step(c)
            else:
                with torch.no_grad():
                    _batch_step(c)
            # Release per-batch references so allocator can reuse.
            del c
            if torch.cuda.is_available() and (b % 16 == 0):
                torch.cuda.empty_cache()

        n_total = max(1, len(ds))
        def _f1(tp: int, fp: int, fn: int) -> float:
            if tp + fp == 0 or tp + fn == 0:
                return 0.0
            prec = tp / (tp + fp)
            rec = tp / (tp + fn)
            if prec + rec == 0:
                return 0.0
            return 2 * prec * rec / (prec + rec)

        return {
            "loss": totals["loss"] / n_total,
            "policy_loss": totals["policy"] / n_total,
            "threat_loss": totals["threat"] / n_total,
            "win_loss": totals["win"] / n_total,
            "fork_loss": totals["fork"] / n_total,
            "pot_loss": totals["pot"] / n_total,
            "value_loss": totals["value"] / n_total,
            "policy_acc": (
                totals["policy_correct"] / max(1, totals["policy_total"])
            ),
            "threat_f1": _f1(totals["threat_tp"], totals["threat_fp"], totals["threat_fn"]),
            "win_f1": _f1(totals["win_tp"], totals["win_fp"], totals["win_fn"]),
            "value_mse": totals["value_sq_err"] / max(1, totals["value_n"]),
            "value_sign_acc": (
                totals["value_sign_correct"] / max(1, totals["value_sign_total"])
            ),
        }

    for ep in range(epochs):
        tr = _run_split(train_ds, train=True, keys=train_keys)
        history["epoch"].append(ep)
        history["train_loss"].append(tr["loss"])
        history["train_policy_acc"].append(tr["policy_acc"])
        history["train_threat_f1"].append(tr["threat_f1"])
        history["train_win_f1"].append(tr["win_f1"])
        history["train_value_mse"].append(tr["value_mse"])
        history["train_value_sign_acc"].append(tr["value_sign_acc"])
        log = (f"ep{ep:03d}  tr loss={tr['loss']:.4f}"
               f"  pol_acc={tr['policy_acc']:.3f}"
               f"  thr_f1={tr['threat_f1']:.3f}"
               f"  win_f1={tr['win_f1']:.3f}"
               f"  v_mse={tr['value_mse']:.3f}"
               f"  v_sign={tr['value_sign_acc']:.3f}")
        if ep % val_every == 0 or ep == epochs - 1:
            va = _run_split(val_ds, train=False, keys=val_keys)
            history["val_loss"].append(va["loss"])
            history["val_policy_acc"].append(va["policy_acc"])
            history["val_threat_f1"].append(va["threat_f1"])
            history["val_win_f1"].append(va["win_f1"])
            history["val_value_mse"].append(va["value_mse"])
            history["val_value_sign_acc"].append(va["value_sign_acc"])
            log += (f"  |  va loss={va['loss']:.4f}"
                    f"  pol_acc={va['policy_acc']:.3f}"
                    f"  thr_f1={va['threat_f1']:.3f}"
                    f"  win_f1={va['win_f1']:.3f}"
                    f"  v_mse={va['value_mse']:.3f}"
                    f"  v_sign={va['value_sign_acc']:.3f}")
        else:
            history["val_loss"].append(float("nan"))
            history["val_policy_acc"].append(float("nan"))
            history["val_threat_f1"].append(float("nan"))
            history["val_win_f1"].append(float("nan"))
            history["val_value_mse"].append(float("nan"))
            history["val_value_sign_acc"].append(float("nan"))
        print(log)

    return model, history
