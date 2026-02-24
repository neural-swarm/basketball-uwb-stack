from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .analytics import PlayerAnalytics, TeamAnalytics
from .clocks import AffineClockMapper
from .config import DemoConfig
from .sensor_fusion import CvKalman2D
from .models import Envelope, FusedState, ImuMeasurement, LpsMeasurement, SourceKind, TeamFrame, TeamMetrics
from .storage import NdjsonSink


@dataclass(slots=True)
class PlayerTracker:
    """Per-player stateful pipeline component.

    Composition here mirrors how a production system usually evolves:
    - device protocol adapters -> measurements
    - clock alignment
    - fusion filter
    - analytics
    """

    player_id: int
    cfg: DemoConfig
    lps_clock: AffineClockMapper = field(default_factory=AffineClockMapper)
    imu_clock: AffineClockMapper = field(default_factory=AffineClockMapper)
    filter: CvKalman2D | None = None
    analytics: PlayerAnalytics | None = None
    last_state: FusedState | None = None

    def __post_init__(self) -> None:
        self.filter = CvKalman2D(player_id=self.player_id, cfg=self.cfg.fusion)
        self.analytics = PlayerAnalytics(player_id=self.player_id, court=self.cfg.court)

    def ingest(self, env: Envelope) -> FusedState:
        if env.source is SourceKind.LPS:
            self.lps_clock.observe(env.source_ts_ns, env.ingest_ts_ns)
            aligned_t = self.lps_clock.map_ts(env.source_ts_ns)
            m = LpsMeasurement(
                player_id=env.player_id,
                t_ns=aligned_t,
                x_m=float(env.payload["x_m"]),
                y_m=float(env.payload["y_m"]),
                quality=float(env.payload.get("quality", 1.0)),
            )
            state = self.filter.ingest_lps(m)
        elif env.source is SourceKind.IMU:
            self.imu_clock.observe(env.source_ts_ns, env.ingest_ts_ns)
            aligned_t = self.imu_clock.map_ts(env.source_ts_ns)
            m = ImuMeasurement(
                player_id=env.player_id,
                t_ns=aligned_t,
                ax_mps2=float(env.payload["ax_mps2"]),
                ay_mps2=float(env.payload["ay_mps2"]),
            )
            state = self.filter.ingest_imu(m)
        else:
            raise ValueError(f"Unsupported source: {env.source}")

        self.analytics.ingest(state)
        self.last_state = state
        return state


class TrackingEngine:
    """Orchestrates multi-player ingestion, fusion, and team analytics."""

    def __init__(self, cfg: DemoConfig) -> None:
        self.cfg = cfg
        self.trackers: dict[int, PlayerTracker] = {
            pid: PlayerTracker(player_id=pid, cfg=cfg)
            for pid in range(1, cfg.players_on_court + 1)
        }
        self.team_analytics = TeamAnalytics()
        self.team_metrics_history: list[TeamMetrics] = []
        self.player_state_history: list[FusedState] = []

    def run(self, events: Iterable[Envelope]) -> None:
        sink: NdjsonSink | None = None
        if self.cfg.output.write_ndjson:
            out_path = Path(self.cfg.output.output_dir) / "tracking_stream.ndjson"
            sink = NdjsonSink(out_path)

        try:
            next_team_tick_ns = 0
            team_tick_dt_ns = int(1e9 / self.cfg.timing.pipeline_tick_hz)

            for env in events:
                tracker = self.trackers[env.player_id]
                state = tracker.ingest(env)
                self.player_state_history.append(state)
                if sink is not None:
                    sink.write_state(state)

                # Emit synchronized team metrics on a regular cadence using latest states.
                while state.t_ns >= next_team_tick_ns:
                    frame_players = [t.last_state for t in self.trackers.values() if t.last_state is not None]
                    if frame_players:
                        frame = TeamFrame(t_ns=next_team_tick_ns, players=list(frame_players))
                        tm = self.team_analytics.compute(frame)
                        self.team_metrics_history.append(tm)
                        if sink is not None:
                            sink.write_team_metrics(tm)
                    next_team_tick_ns += team_tick_dt_ns
        finally:
            if sink is not None:
                sink.close()

    def summarize(self) -> dict[str, object]:
        player_summaries = {
            pid: tracker.analytics.summary
            for pid, tracker in self.trackers.items()
            if tracker.analytics is not None
        }
        avg_mean_pair = (
            sum(m.mean_pair_distance_m for m in self.team_metrics_history) / len(self.team_metrics_history)
            if self.team_metrics_history
            else 0.0
        )
        return {
            "players": player_summaries,
            "team_frames": len(self.team_metrics_history),
            "avg_mean_pair_distance_m": avg_mean_pair,
            "stream_events": len(self.player_state_history),
        }
