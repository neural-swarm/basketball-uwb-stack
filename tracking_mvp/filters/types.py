from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(slots=True, frozen=True)
class AnchorSpec:
    """Static anchor geometry in a local court coordinate frame."""

    anchor_id: str
    x_m: float
    y_m: float
    z_m: float = 0.0


@dataclass(slots=True)
class AnchorReception:
    """One anchor receiving one UWB frame from one tag.

    `rx_time_s` is assumed to be in a common time base (or close enough after lower-level sync).
    Quality fields are optional because different anchor vendors expose different diagnostics.
    """

    anchor_id: str
    tag_id: str
    frame_id: int
    rx_time_s: float
    rssi_dbm: float | None = None
    fp_power_dbm: float | None = None
    sync_quality: float | None = None
    flags: set[str] = field(default_factory=set)


@dataclass(slots=True)
class TdoaObservation:
    """TDoA observation relative to a chosen reference anchor.

    `delta_range_m[anchor]` stores (range_to_anchor - range_to_ref) in meters.
    """

    tag_id: str
    frame_id: int
    t_ref_s: float
    ref_anchor_id: str
    delta_range_m: dict[str, float]
    weights: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class PositionEstimate:
    """Position candidate produced by multilateration before tracking."""

    tag_id: str
    frame_id: int
    t_s: float
    x_m: float
    y_m: float
    residual_rms_m: float
    covariance_xy: tuple[tuple[float, float], tuple[float, float]]
    used_anchor_ids: tuple[str, ...]
    debug: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class TrackState:
    """Common track state used by tutorial Kalman and IMM wrappers."""

    t_s: float
    x_m: float
    y_m: float
    vx_mps: float
    vy_mps: float
    covariance: tuple[tuple[float, ...], ...]
    model_probs: tuple[float, ...] | None = None
    debug: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class SyncStatus:
    """Anchor sync health as seen by the upper pipeline."""

    anchor_id: str
    last_update_s: float
    quality: float
    healthy: bool
    reason: str = "ok"


@dataclass(slots=True)
class PredictedState:
    """Lightweight prediction used by gating and multilateration initialization."""

    t_s: float
    x_m: float
    y_m: float
    vx_mps: float = 0.0
    vy_mps: float = 0.0
    cov_xx: float = 1.0
    cov_yy: float = 1.0


@dataclass(slots=True)
class GatingDecision:
    """Result of quality and gating checks before tracker update."""

    accepted: bool
    reason: str
    score: float
    adjusted_covariance_xy: tuple[tuple[float, float], tuple[float, float]] | None = None


def mean(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0
