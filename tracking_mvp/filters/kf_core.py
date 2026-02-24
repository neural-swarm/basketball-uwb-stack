from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass(slots=True)
class LinearKalmanCore:
    """Minimal reusable linear Kalman filter core.

    This class intentionally knows nothing about anchors, IMU, LPS, or sports tracking.
    Callers provide the dynamic/measurement matrices for each step.
    """

    x: np.ndarray = field(default_factory=lambda: np.zeros((4, 1), dtype=float))
    P: np.ndarray = field(default_factory=lambda: np.eye(4, dtype=float))

    def predict(
        self,
        F: np.ndarray,
        Q: np.ndarray,
        B: np.ndarray | None = None,
        u: np.ndarray | None = None,
    ) -> None:
        """Linear predict step: x = F x (+ B u), P = F P F' + Q."""

        self.x = F @ self.x
        if B is not None and u is not None:
            self.x = self.x + B @ u
        self.P = F @ self.P @ F.T + Q

    def innovation(self, z: np.ndarray, H: np.ndarray, R: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Return innovation and innovation covariance for a measurement."""

        y = z - H @ self.x
        S = H @ self.P @ H.T + R
        return y, S

    def update(self, z: np.ndarray, H: np.ndarray, R: np.ndarray, joseph: bool = True) -> tuple[np.ndarray, np.ndarray]:
        """Linear update step.

        Returns:
            (innovation, innovation_covariance)
        """

        y, S = self.innovation(z, H, R)
        K = self.P @ H.T @ np.linalg.inv(S)
        self.x = self.x + K @ y

        I = np.eye(self.P.shape[0], dtype=float)
        if joseph:
            # Joseph form is numerically safer for tutorial experiments and repeated updates.
            self.P = (I - K @ H) @ self.P @ (I - K @ H).T + K @ R @ K.T
        else:
            self.P = (I - K @ H) @ self.P
        return y, S
