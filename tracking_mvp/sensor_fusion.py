from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .config import FusionConfig
from .filters.kf_core import LinearKalmanCore
from .models import FusedState, ImuMeasurement, LpsMeasurement


@dataclass(slots=True)
class CvKalman2D:
    """Sensor-fusion tracker using a 2D constant-velocity Kalman model.

    This class is the *policy/orchestration* layer around a reusable linear Kalman core:
    - IMU samples drive prediction via acceleration control input
    - LPS/TDoA-derived positions drive measurement updates
    - sensor quality is converted into measurement covariance scaling

    State: [x, y, vx, vy]
    """

    player_id: int
    cfg: FusionConfig
    core: LinearKalmanCore = field(
        default_factory=lambda: LinearKalmanCore(
            x=np.zeros((4, 1), dtype=float),
            P=np.diag([4.0, 4.0, 2.0, 2.0]).astype(float),
        )
    )
    last_t_ns: int | None = None
    last_ax: float = 0.0
    last_ay: float = 0.0

    def ingest_imu(self, m: ImuMeasurement) -> FusedState:
        self._predict_to(m.t_ns)
        self.last_ax, self.last_ay = m.ax_mps2, m.ay_mps2
        return self.state(t_ns=m.t_ns, lps_update_applied=False)

    def ingest_lps(self, m: LpsMeasurement) -> FusedState:
        self._predict_to(m.t_ns)

        H = np.array([[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]], dtype=float)
        z = np.array([[m.x_m], [m.y_m]], dtype=float)

        rv = (self.cfg.meas_pos_std_m / max(m.quality, 1e-3)) ** 2
        R = np.array([[rv, 0.0], [0.0, rv]], dtype=float)

        try:
            self.core.update(z=z, H=H, R=R, joseph=False)
            applied = True
        except np.linalg.LinAlgError:
            # Keep the tracker alive if S becomes singular in a pathological tutorial scenario.
            applied = False

        return self.state(t_ns=m.t_ns, lps_update_applied=applied)

    def _predict_to(self, t_ns: int) -> None:
        if self.last_t_ns is None:
            self.last_t_ns = t_ns
            return

        dt = max(0.0, (t_ns - self.last_t_ns) / 1e9)
        if dt <= 0.0:
            return
        dt = min(dt, self.cfg.max_prediction_gap_s)
        self.last_t_ns = t_ns

        F = np.array(
            [
                [1.0, 0.0, dt, 0.0],
                [0.0, 1.0, 0.0, dt],
                [0.0, 0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ],
            dtype=float,
        )
        B = np.array(
            [
                [0.5 * dt * dt, 0.0],
                [0.0, 0.5 * dt * dt],
                [dt, 0.0],
                [0.0, dt],
            ],
            dtype=float,
        )
        u = np.array([[self.last_ax], [self.last_ay]], dtype=float)

        q = float(self.cfg.process_accel_std_mps2) ** 2
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
        self.core.predict(F=F, Q=Q, B=B, u=u)

    def state(self, t_ns: int, lps_update_applied: bool) -> FusedState:
        x = self.core.x
        P = self.core.P
        return FusedState(
            player_id=self.player_id,
            t_ns=t_ns,
            x_m=float(x[0, 0]),
            y_m=float(x[1, 0]),
            vx_mps=float(x[2, 0]),
            vy_mps=float(x[3, 0]),
            ax_mps2=self.last_ax,
            ay_mps2=self.last_ay,
            lps_update_applied=lps_update_applied,
            debug={"p_x": float(P[0, 0]), "p_y": float(P[1, 1])},
        )
