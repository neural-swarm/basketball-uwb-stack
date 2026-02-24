from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .kf_core import LinearKalmanCore
from .types import PositionEstimate, PredictedState, TrackState


@dataclass(slots=True)
class PositionKalmanTracker2D:
    """Tutorial 2D constant-velocity Kalman tracker.

    State vector: [x, y, vx, vy].
    Measurements: position only (x, y) from multilateration.

    The reusable predict/update math lives in ``LinearKalmanCore``; this wrapper only builds model-specific matrices and keeps tracker state/time semantics for the tutorial pipeline.
    """

    process_accel_std_mps2: float = 2.5
    init_pos_var: float = 4.0
    init_vel_var: float = 9.0
    max_dt_s: float = 0.2
    core: LinearKalmanCore = field(default_factory=lambda: LinearKalmanCore(
        x=np.zeros((4, 1), dtype=float),
        P=np.diag([4.0, 4.0, 9.0, 9.0]).astype(float),
    ))
    _last_t_s: float | None = None
    _initialized: bool = False

    @property
    def _x(self) -> np.ndarray:
        """Compatibility view used by the tutorial IMM implementation."""

        return self.core.x

    @_x.setter
    def _x(self, value: np.ndarray) -> None:
        self.core.x = value

    @property
    def _P(self) -> np.ndarray:
        """Compatibility view used by the tutorial IMM implementation."""

        return self.core.P

    @_P.setter
    def _P(self, value: np.ndarray) -> None:
        self.core.P = value

    def initialize(self, t_s: float, x_m: float, y_m: float) -> None:
        """Initialize tracker from the first position measurement."""

        self.core.x = np.array([[x_m], [y_m], [0.0], [0.0]], dtype=float)
        self.core.P = np.diag([self.init_pos_var, self.init_pos_var, self.init_vel_var, self.init_vel_var])
        self._last_t_s = t_s
        self._initialized = True

    def predict(self, t_s: float) -> PredictedState:
        """Run prediction to a target timestamp and return a lightweight predicted state."""

        if not self._initialized:
            return PredictedState(t_s=t_s, x_m=0.0, y_m=0.0)

        self._predict_internal(t_s)
        return self.predicted_state()

    def predicted_state(self) -> PredictedState:
        """Expose predicted state for gating without performing an update."""

        t_s = 0.0 if self._last_t_s is None else self._last_t_s
        return PredictedState(
            t_s=t_s,
            x_m=float(self.core.x[0, 0]),
            y_m=float(self.core.x[1, 0]),
            vx_mps=float(self.core.x[2, 0]),
            vy_mps=float(self.core.x[3, 0]),
            cov_xx=float(self.core.P[0, 0]),
            cov_yy=float(self.core.P[1, 1]),
        )

    def update(
        self,
        m: PositionEstimate,
        covariance_xy: tuple[tuple[float, float], tuple[float, float]] | None = None,
    ) -> TrackState:
        """Update tracker from a position estimate.

        The caller may override measurement covariance after a quality/gating stage inflates it.
        """

        if not self._initialized:
            self.initialize(m.t_s, m.x_m, m.y_m)
            return self.state()

        self._predict_internal(m.t_s)

        z = np.array([[m.x_m], [m.y_m]], dtype=float)
        H = np.array([[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]], dtype=float)
        if covariance_xy is None:
            covariance_xy = m.covariance_xy
        R = np.array(covariance_xy, dtype=float)

        self.core.update(z=z, H=H, R=R, joseph=True)
        return self.state()

    def state(self) -> TrackState:
        P = tuple(tuple(float(v) for v in row) for row in self.core.P.tolist())
        return TrackState(
            t_s=0.0 if self._last_t_s is None else self._last_t_s,
            x_m=float(self.core.x[0, 0]),
            y_m=float(self.core.x[1, 0]),
            vx_mps=float(self.core.x[2, 0]),
            vy_mps=float(self.core.x[3, 0]),
            covariance=P,
            debug={"p_x": float(self.core.P[0, 0]), "p_y": float(self.core.P[1, 1])},
        )

    def _predict_internal(self, t_s: float) -> None:
        if self._last_t_s is None:
            self._last_t_s = t_s
            return

        dt = max(0.0, t_s - self._last_t_s)
        dt = min(dt, self.max_dt_s)
        self._last_t_s = t_s
        if dt <= 0.0:
            return

        F = np.array(
            [
                [1.0, 0.0, dt, 0.0],
                [0.0, 1.0, 0.0, dt],
                [0.0, 0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ],
            dtype=float,
        )
        q = float(self.process_accel_std_mps2) ** 2
        dt2 = dt * dt
        dt3 = dt2 * dt
        dt4 = dt2 * dt2
        Q = np.array(
            [
                [0.25 * dt4 * q, 0.0, 0.5 * dt3 * q, 0.0],
                [0.0, 0.25 * dt4 * q, 0.0, 0.5 * dt3 * q],
                [0.5 * dt3 * q, 0.0, dt2 * q, 0.0],
                [0.0, 0.5 * dt3 * q, 0.0, dt2 * q],
            ],
            dtype=float,
        )

        self.core.predict(F=F, Q=Q)
