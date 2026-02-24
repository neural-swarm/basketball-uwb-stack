from __future__ import annotations

from dataclasses import dataclass
import heapq
import math
import random
from typing import Iterator

from .config import DemoConfig
from .models import Envelope, SourceKind


@dataclass(slots=True)
class _PlayerMotion:
    """Deterministic path generator with smooth pseudo-basketball movement."""

    phase: float
    freq_x: float
    freq_y: float
    amp_x: float
    amp_y: float
    base_x: float
    base_y: float

    def state(self, t: float) -> tuple[float, float, float, float, float, float]:
        # Position
        x = self.base_x + self.amp_x * math.sin(self.freq_x * t + self.phase)
        y = self.base_y + self.amp_y * math.sin(self.freq_y * t + self.phase * 1.7)
        # Velocity
        vx = self.amp_x * self.freq_x * math.cos(self.freq_x * t + self.phase)
        vy = self.amp_y * self.freq_y * math.cos(self.freq_y * t + self.phase * 1.7)
        # Acceleration
        ax = -self.amp_x * (self.freq_x**2) * math.sin(self.freq_x * t + self.phase)
        ay = -self.amp_y * (self.freq_y**2) * math.sin(self.freq_y * t + self.phase * 1.7)
        return x, y, vx, vy, ax, ay


class DemoStreamFactory:
    """Generates merged LPS/IMU envelopes with realistic-ish jitter and clock skew."""

    def __init__(self, cfg: DemoConfig) -> None:
        self.cfg = cfg
        self.rng = random.Random(cfg.seed)
        self._motions = self._init_motions()

    def _init_motions(self) -> dict[int, _PlayerMotion]:
        motions: dict[int, _PlayerMotion] = {}
        c = self.cfg.court
        for player_id in range(1, self.cfg.players_on_court + 1):
            motions[player_id] = _PlayerMotion(
                phase=self.rng.uniform(0.0, math.tau),
                freq_x=self.rng.uniform(0.25, 0.9),
                freq_y=self.rng.uniform(0.25, 1.1),
                amp_x=self.rng.uniform(2.0, c.width_m * 0.35),
                amp_y=self.rng.uniform(3.0, c.length_m * 0.35),
                base_x=self.rng.uniform(c.width_m * 0.2, c.width_m * 0.8),
                base_y=self.rng.uniform(c.length_m * 0.15, c.length_m * 0.85),
            )
        return motions

    def _clip_to_court(self, x: float, y: float) -> tuple[float, float]:
        x = max(0.0, min(self.cfg.court.width_m, x))
        y = max(0.0, min(self.cfg.court.length_m, y))
        return x, y

    def generate(self) -> Iterator[Envelope]:
        timing = self.cfg.timing
        noise = self.cfg.noise
        duration_s = timing.duration_s

        lps_dt = 1.0 / timing.lps_rate_hz
        imu_dt = 1.0 / timing.imu_rate_hz

        # We merge events by ingest timestamp so the pipeline sees an interleaved stream.
        heap: list[tuple[int, int, Envelope]] = []
        seq = 0

        for player_id, motion in self._motions.items():
            # LPS samples
            t = 0.0
            while t <= duration_s + 1e-9:
                x, y, _, _, _, _ = motion.state(t)
                x, y = self._clip_to_court(x, y)
                if self.rng.random() >= noise.lps_dropout_probability:
                    xn = x + self.rng.gauss(0.0, noise.lps_position_std_m)
                    yn = y + self.rng.gauss(0.0, noise.lps_position_std_m)
                    quality = 1.0
                    if self.rng.random() < noise.lps_outlier_probability:
                        # Outliers are tagged with lower quality so downstream code can decide
                        # whether to down-weight or reject them.
                        ang = self.rng.uniform(0.0, math.tau)
                        rad = self.rng.uniform(0.5, noise.lps_outlier_radius_m)
                        xn += rad * math.cos(ang)
                        yn += rad * math.sin(ang)
                        quality = 0.35
                    xn, yn = self._clip_to_court(xn, yn)

                    source_ts_ns = self._source_ts_ns(
                        t, ppm=timing.lps_clock_ppm, offset_ms=timing.clock_offset_ms
                    )
                    ingest_ts_ns = self._ingest_ts_ns(t, source_kind=SourceKind.LPS)
                    env = Envelope(
                        player_id=player_id,
                        source=SourceKind.LPS,
                        source_ts_ns=source_ts_ns,
                        ingest_ts_ns=ingest_ts_ns,
                        payload={"x_m": xn, "y_m": yn, "quality": quality},
                    )
                    heapq.heappush(heap, (ingest_ts_ns, seq, env))
                    seq += 1
                t += lps_dt

            # IMU samples
            t = 0.0
            while t <= duration_s + 1e-9:
                _, _, _, _, ax, ay = motion.state(t)
                ax += self.rng.gauss(0.0, noise.imu_accel_std_mps2)
                ay += self.rng.gauss(0.0, noise.imu_accel_std_mps2)
                source_ts_ns = self._source_ts_ns(
                    t, ppm=timing.imu_clock_ppm, offset_ms=-timing.clock_offset_ms * 0.4
                )
                ingest_ts_ns = self._ingest_ts_ns(t, source_kind=SourceKind.IMU)
                env = Envelope(
                    player_id=player_id,
                    source=SourceKind.IMU,
                    source_ts_ns=source_ts_ns,
                    ingest_ts_ns=ingest_ts_ns,
                    payload={"ax_mps2": ax, "ay_mps2": ay},
                )
                heapq.heappush(heap, (ingest_ts_ns, seq, env))
                seq += 1
                t += imu_dt

        while heap:
            _, _, env = heapq.heappop(heap)
            yield env




    def generate_imu_only(self) -> Iterator[Envelope]:
        """Generate only IMU envelopes, merged across players by ingest timestamp.

        This is useful when an upstream positioning stack (e.g., UWB TDoA) provides positions and we
        still want IMU-driven dynamics in the fusion filter.
        """
        timing = self.cfg.timing
        imu_dt = 1.0 / timing.imu_rate_hz

        heap: list[tuple[int, int, Envelope]] = []
        seq = 0

        for player_id, motion in self._motions.items():
            t = 0.0
            while t <= timing.duration_s + 1e-9:
                _, _, _, _, ax, ay = motion.state(t)
                source_ts_ns = self._source_ts_ns(
                    t, ppm=timing.imu_clock_ppm, offset_ms=timing.clock_offset_ms
                )
                ingest_ts_ns = self._ingest_ts_ns(t, SourceKind.IMU)
                env = Envelope(
                    player_id=player_id,
                    source=SourceKind.IMU,
                    source_ts_ns=source_ts_ns,
                    ingest_ts_ns=ingest_ts_ns,
                    payload={
                        "ax_mps2": ax + self.rng.gauss(0.0, self.cfg.noise.imu_accel_std_mps2),
                        "ay_mps2": ay + self.rng.gauss(0.0, self.cfg.noise.imu_accel_std_mps2),
                    },
                )
                heapq.heappush(heap, (ingest_ts_ns, seq, env))
                seq += 1
                t += imu_dt

        while heap:
            _, _, env = heapq.heappop(heap)
            yield env

    def generate_tdoa_positions(self) -> Iterator[Envelope]:
        """Generate IMU envelopes + *TDoA-derived* pseudo-LPS envelopes.

        This method demonstrates how the tutorial `tracking_mvp.filters` modules can feed into the
        existing fusion/analytics pipeline:

          anchor receptions -> TDoA -> multilateration -> quality gates -> Envelope(SourceKind.LPS)

        Assumptions (tutorial):
        - Anchor timestamps are already in a common time base (e.g., vendor sync is enabled).
        - We simulate anchor receptions from the same underlying ground-truth motion as the IMU.

        The output is still an `Envelope` stream, so `TrackingEngine` does not need to change.
        """
        # Import locally to keep the core simulation lightweight when not used.
        from .filters.tdoa_builder import TdoaBuilder, SPEED_OF_LIGHT_MPS
        from .filters.multilateration import TdoaMultilateration2D
        from .filters.quality_filters import MeasurementQualityFilter
        from .filters.types import AnchorReception, AnchorSpec, PredictedState

        cfg = self.cfg
        timing = cfg.timing
        noise = cfg.noise

        # A simple 6-anchor layout (corners + mid-sides). Real deployments often place anchors at
        # height; we keep a small z to make the range model realistic-ish.
        c = cfg.court
        anchors: dict[str, AnchorSpec] = {
            "A1": AnchorSpec("A1", 0.0, 0.0, 3.0),
            "A2": AnchorSpec("A2", c.width_m, 0.0, 3.0),
            "A3": AnchorSpec("A3", 0.0, c.length_m, 3.0),
            "A4": AnchorSpec("A4", c.width_m, c.length_m, 3.0),
            "A5": AnchorSpec("A5", c.width_m / 2.0, 0.0, 3.0),
            "A6": AnchorSpec("A6", c.width_m / 2.0, c.length_m, 3.0),
        }

        builder = TdoaBuilder(min_anchors_per_frame=4, reference_policy="earliest")
        solver = TdoaMultilateration2D()
        qf = MeasurementQualityFilter()

        # Timing: we simulate one UWB frame per "LPS tick".
        lps_dt = 1.0 / timing.lps_rate_hz

        # Reception timestamp noise: ~0.6 ns gives ~18 cm range noise.
        # This is intentionally not tuned; it's here to make errors visible.
        rx_time_std_s = 0.6e-9

        # We merge IMU + position envelopes by ingest timestamp like the base demo.
        heap: list[tuple[int, int, Envelope]] = []
        seq = 0

        # 1) Push IMU events first.
        for env in self.generate_imu_only():
            heapq.heappush(heap, (env.ingest_ts_ns, seq, env))
            seq += 1

        # 2) Simulate anchor receptions, solve TDoA, emit pseudo-LPS envelopes.
        last_prior: dict[int, PredictedState] = {}

        frame_id = 0
        t = 0.0
        while t <= timing.duration_s + 1e-9:
            frame_id += 1
            for player_id, motion in self._motions.items():
                x, y, vx, vy, _, _ = motion.state(t)
                x, y = self._clip_to_court(x, y)

                # Build one reception per anchor. In reality some receptions will be missing; we
                # keep it simple and let quality gates handle occasional issues.
                receptions: list[AnchorReception] = []
                tag_id = f"p{player_id}"

                # Emission time in the common clock.
                t_emit = t

                for a in anchors.values():
                    # 3D range model (even though we solve in 2D).
                    dx = x - a.x_m
                    dy = y - a.y_m
                    dz = 0.0 - a.z_m
                    rng = (dx * dx + dy * dy + dz * dz) ** 0.5

                    # Occasionally inject an NLOS-like positive bias for one random anchor.
                    # This produces exactly the kind of "teleport" points that robust pipelines
                    # must handle.
                    if self.rng.random() < 0.02:
                        rng += self.rng.uniform(0.5, 2.0)

                    rx_time = t_emit + (rng / SPEED_OF_LIGHT_MPS) + self.rng.gauss(0.0, rx_time_std_s)

                    receptions.append(
                        AnchorReception(
                            anchor_id=a.anchor_id,
                            tag_id=tag_id,
                            frame_id=frame_id,
                            rx_time_s=rx_time,
                            # Fake diagnostics so quality filters have something to look at.
                            rssi_dbm=-70.0 + self.rng.gauss(0.0, 2.5),
                            fp_power_dbm=-76.0 + self.rng.gauss(0.0, 2.5),
                            sync_quality=1.0,
                        )
                    )

                receptions = qf.mark_suspect_nlos(receptions)
                obs = builder.build_one(receptions)
                if obs is None:
                    continue

                prior = last_prior.get(player_id)
                est = solver.solve(obs, anchors=anchors, prior=prior)
                if est is None:
                    continue

                # Use a lightweight gate before forwarding into the main fusion filter.
                decision = qf.gate_position(est, predicted=prior)

                if not decision.accepted:
                    continue

                # Convert to an LPS-style envelope consumed by PlayerTracker.
                source_ts_ns = self._source_ts_ns(
                    t, ppm=timing.lps_clock_ppm, offset_ms=timing.clock_offset_ms
                )
                ingest_ts_ns = self._ingest_ts_ns(t, SourceKind.IMU)

                # Quality: inverse residual + optional inflation from gating.
                q = 1.0 / (1.0 + max(0.0, est.residual_rms_m))
                env = Envelope(
                    player_id=player_id,
                    source=SourceKind.LPS,
                    source_ts_ns=source_ts_ns,
                    ingest_ts_ns=ingest_ts_ns,
                    payload={"x_m": est.x_m, "y_m": est.y_m, "quality": float(q)},
                )
                heapq.heappush(heap, (ingest_ts_ns, seq, env))
                seq += 1

                # Update prior for next frame based on true dynamics for the tutorial.
                last_prior[player_id] = PredictedState(
                    t_s=t,
                    x_m=est.x_m,
                    y_m=est.y_m,
                    vx_mps=vx,
                    vy_mps=vy,
                    cov_xx=est.covariance_xy[0][0],
                    cov_yy=est.covariance_xy[1][1],
                )
            t += lps_dt

        while heap:
            _, _, env = heapq.heappop(heap)
            yield env

    def _source_ts_ns(self, t_s: float, ppm: float, offset_ms: float) -> int:
        drift = 1.0 + ppm * 1e-6
        jitter_s = self.rng.uniform(-0.0004, 0.0004)
        return int((t_s * drift + offset_ms / 1e3 + jitter_s) * 1e9)

    def _ingest_ts_ns(self, t_s: float, source_kind: SourceKind) -> int:
        # Simulate transport and scheduling latency. IMU packets arrive slightly faster.
        base_ms = 9.5 if source_kind is SourceKind.LPS else 4.0
        jitter_ms = self.rng.uniform(-2.0, 4.0)
        return int((t_s + max(0.2, base_ms + jitter_ms) / 1e3) * 1e9)
