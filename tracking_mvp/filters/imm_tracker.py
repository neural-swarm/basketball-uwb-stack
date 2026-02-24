from __future__ import annotations

from dataclasses import dataclass, field
from math import exp, pi

import numpy as np

from .kalman_tracker import PositionKalmanTracker2D
from .types import PositionEstimate, TrackState


@dataclass(slots=True)
class ImmTracker2D:
    """Tutorial IMM (Interacting Multiple Model) tracker for 2D position tracking.

    This version uses the same state dimension for all models and differentiates them by process
    noise ("calm" vs "agile" motion assumptions). That keeps the implementation compact while still
    demonstrating the IMM mechanics: interaction, model likelihoods, and probability updates.
    """

    process_noises_mps2: tuple[float, ...] = (1.0, 4.0, 8.0)
    transition_matrix: tuple[tuple[float, ...], ...] | None = None
    _trackers: list[PositionKalmanTracker2D] = field(default_factory=list)
    _mu: np.ndarray | None = None
    _initialized: bool = False
    _last_mix_normalizer: np.ndarray | None = None

    def __post_init__(self) -> None:
        if not self._trackers:
            self._trackers = [
                PositionKalmanTracker2D(process_accel_std_mps2=q) for q in self.process_noises_mps2
            ]
        n = len(self._trackers)
        if self.transition_matrix is None:
            stay = 0.90
            switch = (1.0 - stay) / max(n - 1, 1)
            tm = [[switch for _ in range(n)] for _ in range(n)]
            for i in range(n):
                tm[i][i] = stay
            self.transition_matrix = tuple(tuple(row) for row in tm)
        self._mu = np.full((n,), 1.0 / n, dtype=float)

    def predict(self, t_s: float) -> TrackState:
        """Predict all models to a timestamp and return the mixed state."""

        if not self._initialized:
            # Return a neutral empty state before the first measurement.
            return TrackState(t_s=t_s, x_m=0.0, y_m=0.0, vx_mps=0.0, vy_mps=0.0, covariance=((1.0, 0.0, 0.0, 0.0), (0.0, 1.0, 0.0, 0.0), (0.0, 0.0, 1.0, 0.0), (0.0, 0.0, 0.0, 1.0)), model_probs=tuple(float(v) for v in self._mu))
        self._mix_and_predict(t_s)
        return self.state()

    def update(self, m: PositionEstimate, covariance_xy: tuple[tuple[float, float], tuple[float, float]] | None = None) -> TrackState:
        """IMM update from a position measurement.

        The pipeline should apply quality gates before calling this method. IMM expects the measurement
        to be plausible (or at least covariance-inflated if suspicious).
        """

        if not self._initialized:
            for tr in self._trackers:
                tr.initialize(m.t_s, m.x_m, m.y_m)
            self._initialized = True
            return self.state()

        self._mix_and_predict(m.t_s)
        z = np.array([[m.x_m], [m.y_m]], dtype=float)
        H = np.array([[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]], dtype=float)
        R = np.array(m.covariance_xy if covariance_xy is None else covariance_xy, dtype=float)

        likelihoods: list[float] = []
        for tr in self._trackers:
            # Likelihood is computed on the predicted state before the model-specific update.
            x = tr._x
            P = tr._P
            innov = z - H @ x
            S = H @ P @ H.T + R
            like = self._gaussian_likelihood_2d(innov, S)
            likelihoods.append(like)
            tr.update(m, covariance_xy=tuple(tuple(float(v) for v in row) for row in R.tolist()))

        mu_pred = self._last_mix_normalizer if self._last_mix_normalizer is not None else self._mu
        post = mu_pred * np.array(likelihoods, dtype=float)
        total = float(np.sum(post))
        if total <= 0.0:
            self._mu = np.full_like(post, 1.0 / len(post))
        else:
            self._mu = post / total
        return self.state()

    def state(self) -> TrackState:
        """Return the probability-weighted mixed state across models."""

        x_mix, P_mix = self._combine_states(self._mu)
        return TrackState(
            t_s=0.0 if self._trackers[0]._last_t_s is None else float(self._trackers[0]._last_t_s),
            x_m=float(x_mix[0, 0]),
            y_m=float(x_mix[1, 0]),
            vx_mps=float(x_mix[2, 0]),
            vy_mps=float(x_mix[3, 0]),
            covariance=tuple(tuple(float(v) for v in row) for row in P_mix.tolist()),
            model_probs=tuple(float(v) for v in self._mu.tolist()),
            debug={f"mu_{i}": float(v) for i, v in enumerate(self._mu.tolist())},
        )

    def _mix_and_predict(self, t_s: float) -> None:
        """Perform the IMM interaction (mixing) and model-wise prediction step."""

        for tr in self._trackers:
            tr.predict(t_s)

        Pi = np.array(self.transition_matrix, dtype=float)
        mu_prev = self._mu.copy()
        mu_pred = mu_prev @ Pi
        self._last_mix_normalizer = mu_pred

        xs = [tr._x.copy() for tr in self._trackers]
        Ps = [tr._P.copy() for tr in self._trackers]
        n = len(self._trackers)

        mixed_xs: list[np.ndarray] = []
        mixed_Ps: list[np.ndarray] = []
        for j in range(n):
            denom = float(mu_pred[j])
            if denom <= 1e-12:
                # Fallback to model's own state if the predicted probability underflows.
                mixed_xs.append(xs[j])
                mixed_Ps.append(Ps[j])
                continue
            mu_ij = (mu_prev * Pi[:, j]) / denom
            x0 = sum(mu_ij[i] * xs[i] for i in range(n))
            P0 = np.zeros((4, 4), dtype=float)
            for i in range(n):
                dx = xs[i] - x0
                P0 += mu_ij[i] * (Ps[i] + dx @ dx.T)
            mixed_xs.append(x0)
            mixed_Ps.append(P0)

        for tr, x0, P0 in zip(self._trackers, mixed_xs, mixed_Ps):
            tr._x = x0
            tr._P = P0
            tr._last_t_s = t_s

    def _combine_states(self, mu: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        xs = [tr._x for tr in self._trackers]
        Ps = [tr._P for tr in self._trackers]
        x_mix = sum(mu[i] * xs[i] for i in range(len(xs)))
        P_mix = np.zeros((4, 4), dtype=float)
        for i in range(len(xs)):
            dx = xs[i] - x_mix
            P_mix += mu[i] * (Ps[i] + dx @ dx.T)
        return x_mix, P_mix

    def _gaussian_likelihood_2d(self, innov: np.ndarray, S: np.ndarray) -> float:
        """Gaussian likelihood of a 2D innovation with covariance S.

        A floor is used to keep tutorial code stable when S becomes nearly singular.
        """

        try:
            det = float(np.linalg.det(S))
            if det <= 1e-12:
                return 1e-12
            invS = np.linalg.inv(S)
            md2 = float((innov.T @ invS @ innov)[0, 0])
            norm = 1.0 / (2.0 * pi * (det ** 0.5))
            return max(1e-12, norm * exp(-0.5 * md2))
        except np.linalg.LinAlgError:
            return 1e-12
