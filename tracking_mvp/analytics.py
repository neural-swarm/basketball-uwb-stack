from __future__ import annotations

from dataclasses import dataclass, field
import math

from .config import CourtConfig
from .models import FusedState, PlayerSummary, TeamFrame, TeamMetrics


@dataclass(slots=True)
class Heatmap:
    """Streaming occupancy grid for one player."""

    court: CourtConfig
    grid: list[list[int]] = field(init=False)

    def __post_init__(self) -> None:
        rows = int(math.ceil(self.court.length_m / self.court.heatmap_cell_m))
        cols = int(math.ceil(self.court.width_m / self.court.heatmap_cell_m))
        self.grid = [[0 for _ in range(cols)] for _ in range(rows)]

    def ingest(self, x_m: float, y_m: float) -> None:
        if x_m < 0.0 or y_m < 0.0:
            return
        r = int(y_m // self.court.heatmap_cell_m)
        c = int(x_m // self.court.heatmap_cell_m)
        if 0 <= r < len(self.grid) and 0 <= c < len(self.grid[0]):
            self.grid[r][c] += 1


@dataclass(slots=True)
class PlayerAnalytics:
    """Incremental per-player metrics updated on fused output frames."""

    player_id: int
    court: CourtConfig
    summary: PlayerSummary = field(init=False)
    heatmap: Heatmap = field(init=False)
    _last_state: FusedState | None = None

    def __post_init__(self) -> None:
        self.summary = PlayerSummary(player_id=self.player_id)
        self.heatmap = Heatmap(self.court)

    def ingest(self, state: FusedState) -> None:
        self.summary.samples += 1
        if state.lps_update_applied:
            self.summary.lps_updates += 1

        speed = math.hypot(state.vx_mps, state.vy_mps)
        accel = math.hypot(state.ax_mps2, state.ay_mps2)
        self.summary.max_speed_mps = max(self.summary.max_speed_mps, speed)
        self.summary.max_accel_mps2 = max(self.summary.max_accel_mps2, accel)

        # Thresholds are placeholders for the tutorial. In production they should be calibrated
        # against sport-specific definitions and sampling/fusion settings.
        if accel > 3.5:
            self.summary.high_accel_events += 1

        if self._last_state is not None:
            dx = state.x_m - self._last_state.x_m
            dy = state.y_m - self._last_state.y_m
            self.summary.total_distance_m += math.hypot(dx, dy)

        self.heatmap.ingest(state.x_m, state.y_m)
        self._last_state = state


class TeamAnalytics:
    """Team-level spacing metrics emitted on synchronized team frames."""

    def compute(self, frame: TeamFrame) -> TeamMetrics:
        if not frame.players:
            return TeamMetrics(frame.t_ns, 0.0, 0.0, 0.0, 0.0)

        xs = [p.x_m for p in frame.players]
        ys = [p.y_m for p in frame.players]
        cx = sum(xs) / len(xs)
        cy = sum(ys) / len(ys)

        pair_dists: list[float] = []
        players = frame.players
        for i in range(len(players)):
            for j in range(i + 1, len(players)):
                dx = players[i].x_m - players[j].x_m
                dy = players[i].y_m - players[j].y_m
                pair_dists.append(math.hypot(dx, dy))

        mean_pair = sum(pair_dists) / len(pair_dists) if pair_dists else 0.0
        max_pair = max(pair_dists) if pair_dists else 0.0
        return TeamMetrics(
            t_ns=frame.t_ns,
            centroid_x_m=cx,
            centroid_y_m=cy,
            mean_pair_distance_m=mean_pair,
            max_pair_distance_m=max_pair,
        )
