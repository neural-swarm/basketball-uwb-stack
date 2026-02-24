from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class NoiseConfig:
    """Noise and dropout profile for simulated devices."""

    lps_position_std_m: float = 0.12
    imu_accel_std_mps2: float = 0.25
    lps_dropout_probability: float = 0.04
    lps_outlier_probability: float = 0.01
    lps_outlier_radius_m: float = 1.25


@dataclass(slots=True)
class CourtConfig:
    """Basketball court dimensions in meters (FIBA-ish defaults)."""

    width_m: float = 15.0
    length_m: float = 28.0
    heatmap_cell_m: float = 0.5


@dataclass(slots=True)
class TimingConfig:
    """Simulated source and system timing rates."""

    duration_s: float = 12.0
    lps_rate_hz: float = 20.0
    imu_rate_hz: float = 100.0
    pipeline_tick_hz: float = 20.0
    # Source timestamp drift/skew is exaggerated a bit to make clock mapping visible.
    lps_clock_ppm: float = 35.0
    imu_clock_ppm: float = -18.0
    clock_offset_ms: float = 7.5


@dataclass(slots=True)
class FusionConfig:
    """Constant-velocity Kalman filter tuning."""

    process_accel_std_mps2: float = 1.4
    meas_pos_std_m: float = 0.18
    max_prediction_gap_s: float = 0.25


@dataclass(slots=True)
class OutputConfig:
    """Optional local outputs for debugging and downstream adapters."""

    write_ndjson: bool = True
    output_dir: Path = field(default_factory=lambda: Path("artifacts"))


@dataclass(slots=True)
class DemoConfig:
    """Top-level tutorial demo configuration."""

    players_on_court: int = 10
    seed: int = 7
    court: CourtConfig = field(default_factory=CourtConfig)
    timing: TimingConfig = field(default_factory=TimingConfig)
    noise: NoiseConfig = field(default_factory=NoiseConfig)
    fusion: FusionConfig = field(default_factory=FusionConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
