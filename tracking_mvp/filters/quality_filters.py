from __future__ import annotations

from dataclasses import dataclass
from math import hypot

from .types import AnchorReception, GatingDecision, PositionEstimate, PredictedState


@dataclass(slots=True)
class MeasurementQualityFilter:
    """Simple quality gates for UWB positioning measurements.

    This module intentionally mixes heuristic checks and statistical checks to show how practical
    RTLS pipelines are often assembled before a more sophisticated quality model is introduced.
    """

    min_rssi_dbm: float = -95.0
    max_fp_gap_db: float = 12.0
    max_position_residual_m: float = 1.5
    max_speed_mps: float = 12.0
    mahalanobis_threshold_sq: float = 16.0  # ~4 sigma in 2D
    inflate_covariance_on_suspect: float = 4.0

    def mark_suspect_nlos(self, receptions: list[AnchorReception]) -> list[AnchorReception]:
        """Add a lightweight NLOS suspicion flag using simple power heuristics.

        If first-path power is much lower than total RSSI, multipath/NLOS is more likely.
        """

        out: list[AnchorReception] = []
        for rx in receptions:
            flags = set(rx.flags)
            if rx.rssi_dbm is not None and rx.rssi_dbm < self.min_rssi_dbm:
                flags.add("weak_signal")
            if rx.rssi_dbm is not None and rx.fp_power_dbm is not None:
                gap = rx.rssi_dbm - rx.fp_power_dbm
                if gap > self.max_fp_gap_db:
                    flags.add("suspect_nlos")
            out.append(
                AnchorReception(
                    anchor_id=rx.anchor_id,
                    tag_id=rx.tag_id,
                    frame_id=rx.frame_id,
                    rx_time_s=rx.rx_time_s,
                    rssi_dbm=rx.rssi_dbm,
                    fp_power_dbm=rx.fp_power_dbm,
                    sync_quality=rx.sync_quality,
                    flags=flags,
                )
            )
        return out

    def prune_receptions(self, receptions: list[AnchorReception]) -> list[AnchorReception]:
        """Drop obviously poor receptions while keeping enough anchors for TDoA."""

        if len(receptions) <= 4:
            return receptions
        good = [r for r in receptions if "weak_signal" not in r.flags]
        if len(good) >= 4:
            return good
        return receptions

    def gate_position(
        self,
        estimate: PositionEstimate,
        predicted: PredictedState | None,
    ) -> GatingDecision:
        """Validate a multilateration result before tracker update.

        The method can reject, accept, or accept with inflated covariance to reduce tracker trust.
        """

        if estimate.residual_rms_m > self.max_position_residual_m:
            return GatingDecision(False, "large_multilateration_residual", estimate.residual_rms_m)

        cov = estimate.covariance_xy
        adjusted_cov = cov
        if estimate.residual_rms_m > 0.5 * self.max_position_residual_m:
            adjusted_cov = self._inflate_cov(cov, self.inflate_covariance_on_suspect)

        if predicted is None:
            return GatingDecision(True, "accepted_no_prediction", estimate.residual_rms_m, adjusted_cov)

        dt = max(1e-6, estimate.t_s - predicted.t_s)
        dx = estimate.x_m - predicted.x_m
        dy = estimate.y_m - predicted.y_m
        apparent_speed = hypot(dx, dy) / dt
        if apparent_speed > self.max_speed_mps:
            return GatingDecision(False, "speed_gate", apparent_speed)

        md2 = self._mahalanobis_sq(estimate, predicted)
        if md2 > self.mahalanobis_threshold_sq:
            return GatingDecision(False, "mahalanobis_gate", md2)

        return GatingDecision(True, "accepted", md2, adjusted_cov)

    def _inflate_cov(
        self,
        cov: tuple[tuple[float, float], tuple[float, float]],
        factor: float,
    ) -> tuple[tuple[float, float], tuple[float, float]]:
        return (
            (cov[0][0] * factor, cov[0][1] * factor),
            (cov[1][0] * factor, cov[1][1] * factor),
        )

    def _mahalanobis_sq(self, estimate: PositionEstimate, predicted: PredictedState) -> float:
        # Tutorial version uses a diagonal approximation combining track and measurement uncertainty.
        vx = max(1e-6, predicted.cov_xx + estimate.covariance_xy[0][0])
        vy = max(1e-6, predicted.cov_yy + estimate.covariance_xy[1][1])
        dx = estimate.x_m - predicted.x_m
        dy = estimate.y_m - predicted.y_m
        return (dx * dx) / vx + (dy * dy) / vy
