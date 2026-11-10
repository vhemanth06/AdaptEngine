"""A2 Bandit Ranking Policy (W8 J.3, D53): LinUCB scores with a softmax, so the selection
probability (propensity) of every candidate is exact and logged.

score_i = w . x_i + alpha * sqrt(x_i' A^-1 x_i),  w = A^-1 b,  A = lambda I + sum x x'
P(i) = softmax(score / tau);  the draw uses a keyed uniform (seed, day, slot, minutes left).
update(x, r): online ridge regression (Sherman-Morrison on A^-1), only in mode "updating".

Modes: "frozen" (weights fixed), "updating" (keeps learning), "random" (uniform propensities).
This is the project's single feedback-driven policy (Assignment §2.2.11). Pure Python.
"""

from __future__ import annotations

import json
import math

from .base import keyed_uniform
from .features import DIM, FEATURE_NAMES, extract

MODES = ("frozen", "updating", "random")


class BanditPolicy:
    def __init__(
        self,
        mode: str = "frozen",
        *,
        lam: float = 1.0,
        alpha: float = 0.3,
        tau: float = 0.1,
        seed: int = 0,
        a_inv=None,
        b=None,
        n_updates: int = 0,
    ):
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
        if not (lam > 0 and tau > 0 and alpha >= 0):
            raise ValueError("lam and tau must be > 0, alpha >= 0")
        self.mode, self.lam, self.alpha, self.tau, self.seed = mode, lam, alpha, tau, seed
        self.a_inv = (
            [list(r) for r in a_inv]
            if a_inv is not None
            else [[(1.0 / lam if i == j else 0.0) for j in range(DIM)] for i in range(DIM)]
        )
        self.b = list(b) if b is not None else [0.0] * DIM
        self.n_updates = n_updates

    @property
    def name(self) -> str:
        return f"bandit_{self.mode}"

    @property
    def version(self) -> str:
        return f"linucb-softmax/{self.mode}/n{self.n_updates}"

    # ---------------------------------------------------------------- linear algebra
    def _matvec(self, x):
        return [sum(r[j] * x[j] for j in range(DIM)) for r in self.a_inv]

    def weights(self) -> list[float]:
        return self._matvec(self.b)

    def scores(self, xs) -> list[float]:
        w = self.weights()
        out = []
        for x in xs:
            ax = self._matvec(x)
            var = max(0.0, sum(xi * ai for xi, ai in zip(x, ax)))
            out.append(sum(wi * xi for wi, xi in zip(w, x)) + self.alpha * math.sqrt(var))
        return out

    def propensities(self, xs) -> list[float]:
        if self.mode == "random":
            return [1.0 / len(xs)] * len(xs)
        s = [v / self.tau for v in self.scores(xs)]
        m = max(s)
        e = [math.exp(v - m) for v in s]
        z = sum(e)
        return [v / z for v in e]

    # ---------------------------------------------------------------- policy interface
    def choose(self, candidates: list[dict], context: dict) -> tuple[str, float, dict]:
        xs = [extract(c, context) for c in candidates]
        probs = self.propensities(xs)
        u = keyed_uniform(
            "bandit",
            self.seed,
            context.get("seed", 0),
            context["day"],
            context["slot"],
            context["remaining_budget"],
        )
        acc, k = 0.0, len(probs) - 1
        for i, pr in enumerate(probs):
            acc += pr
            if u < acc:
                k = i
                break
        info = {
            "propensities": probs,  # exact (OPE needs them unrounded)
            "features": [[round(v, 6) for v in x] for x in xs],
        }
        return candidates[k]["activity_id"], probs[k], info

    def update(self, x, reward: float) -> None:
        """Online ridge update with one (features, reward) pair; frozen/random ignore it."""
        if self.mode != "updating":
            return
        if len(x) != DIM or not all(math.isfinite(v) for v in x) or not math.isfinite(reward):
            raise ValueError("update needs a finite feature vector of length DIM and reward")
        ax = self._matvec(x)
        denom = 1.0 + sum(xi * ai for xi, ai in zip(x, ax))
        for i in range(DIM):
            for j in range(DIM):
                self.a_inv[i][j] -= ax[i] * ax[j] / denom
        self.b = [bi + reward * xi for bi, xi in zip(self.b, x)]
        self.n_updates += 1

    # ---------------------------------------------------------------- persistence
    def to_dict(self) -> dict:
        return {
            "feature_names": list(FEATURE_NAMES),
            "lam": self.lam,
            "alpha": self.alpha,
            "tau": self.tau,
            "a_inv": self.a_inv,
            "b": self.b,
            "n_updates": self.n_updates,
        }

    @classmethod
    def from_dict(cls, d: dict, mode: str = "frozen", seed: int = 0) -> "BanditPolicy":
        if list(d.get("feature_names", [])) != list(FEATURE_NAMES):
            raise ValueError("saved policy has a different feature set")
        return cls(
            mode,
            lam=d["lam"],
            alpha=d["alpha"],
            tau=d["tau"],
            seed=seed,
            a_inv=d["a_inv"],
            b=d["b"],
            n_updates=d["n_updates"],
        )

    def save(self, path: str, meta: dict | None = None) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({**(meta or {}), **self.to_dict()}, f, indent=1)

    @classmethod
    def load(cls, path: str, mode: str = "frozen", seed: int = 0) -> "BanditPolicy":
        with open(path, encoding="utf-8") as f:
            return cls.from_dict(json.load(f), mode=mode, seed=seed)

    def copy(self, mode: str | None = None, seed: int | None = None) -> "BanditPolicy":
        return BanditPolicy.from_dict(
            self.to_dict(), mode=mode or self.mode, seed=self.seed if seed is None else seed
        )
