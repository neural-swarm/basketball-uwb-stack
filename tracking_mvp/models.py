from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SourceKind(str, Enum):
    LPS = "lps"
    IMU = "imu"


@dataclass(slots=True)
class Envelope:
    """Transport-neutral event wrapper used by the pipeline.

    In production this would be created by MQTT/Kafka/UDP adapters.
    `source_ts_ns` is device clock time, while `ingest_ts_ns` is edge-host time.
    """

    player_id: int
    source: SourceKind
    source_ts_ns: int
    ingest_ts_ns: int
    payload: dict[str, Any]


@dataclass(slots=True)
class LpsMeasurement:
    player_id: int
    t_ns: int
    x_m: float
    y_m: float
    quality: float = 1.0


@dataclass(slots=True)
class ImuMeasurement:
    player_id: int
    t_ns: int
    ax_mps2: float
    ay_mps2: float


@dataclass(slots=True)
class FusedState:
    player_id: int
    t_ns: int
    x_m: float
    y_m: float
    vx_mps: float
    vy_mps: float
    ax_mps2: float
    ay_mps2: float
    lps_update_applied: bool = False
    debug: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class PlayerSummary:
    player_id: int
    samples: int = 0
    lps_updates: int = 0
    total_distance_m: float = 0.0
    max_speed_mps: float = 0.0
    max_accel_mps2: float = 0.0
    high_accel_events: int = 0


@dataclass(slots=True)
class TeamFrame:
    t_ns: int
    players: list[FusedState]


@dataclass(slots=True)
class TeamMetrics:
    t_ns: int
    centroid_x_m: float
    centroid_y_m: float
    mean_pair_distance_m: float
    max_pair_distance_m: float
