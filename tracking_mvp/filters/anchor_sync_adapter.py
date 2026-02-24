from __future__ import annotations

from dataclasses import dataclass, field

from .types import AnchorReception, SyncStatus


@dataclass(slots=True)
class AnchorSyncMonitor:
    """Upper-layer monitor for anchor sync health.

    This module does not perform low-level clock synchronization. It assumes the anchor network
    (e.g., UbiTrack-A1 deployment) already provides synchronized or near-synchronized timestamps.
    The goal here is to expose a clean software seam that can drop anchors when sync quality degrades.
    """

    stale_after_s: float = 1.0
    min_quality: float = 0.2
    _status: dict[str, SyncStatus] = field(default_factory=dict)

    def update_from_reception(self, rx: AnchorReception) -> None:
        """Update sync status from anchor metadata attached to a reception.

        If `sync_quality` is missing, we optimistically keep the anchor healthy but still track age.
        """

        quality = 1.0 if rx.sync_quality is None else max(0.0, min(1.0, rx.sync_quality))
        healthy = quality >= self.min_quality
        reason = "ok" if healthy else "low_sync_quality"
        self._status[rx.anchor_id] = SyncStatus(
            anchor_id=rx.anchor_id,
            last_update_s=rx.rx_time_s,
            quality=quality,
            healthy=healthy,
            reason=reason,
        )

    def mark_sync_telemetry(self, anchor_id: str, t_s: float, quality: float, healthy: bool = True) -> None:
        """Optional explicit sync telemetry path when the lower layer emits dedicated sync events."""

        quality = max(0.0, min(1.0, quality))
        if quality < self.min_quality:
            healthy = False
        self._status[anchor_id] = SyncStatus(
            anchor_id=anchor_id,
            last_update_s=t_s,
            quality=quality,
            healthy=healthy,
            reason="ok" if healthy else "sync_unhealthy",
        )

    def is_anchor_usable(self, anchor_id: str, now_s: float) -> bool:
        status = self._status.get(anchor_id)
        if status is None:
            return False
        if (now_s - status.last_update_s) > self.stale_after_s:
            return False
        return status.healthy

    def filter_receptions(self, receptions: list[AnchorReception]) -> list[AnchorReception]:
        """Drop receptions from anchors that are stale/unhealthy in sync state."""

        if not receptions:
            return receptions
        now_s = max(r.rx_time_s for r in receptions)
        out: list[AnchorReception] = []
        for rx in receptions:
            self.update_from_reception(rx)
            if self.is_anchor_usable(rx.anchor_id, now_s=now_s):
                out.append(rx)
        return out

    def snapshot(self, now_s: float | None = None) -> dict[str, SyncStatus]:
        """Return current statuses with staleness reflected in `healthy` flag."""

        if now_s is None and self._status:
            now_s = max(s.last_update_s for s in self._status.values())
        elif now_s is None:
            now_s = 0.0

        snap: dict[str, SyncStatus] = {}
        for anchor_id, s in self._status.items():
            stale = (now_s - s.last_update_s) > self.stale_after_s
            healthy = s.healthy and not stale
            reason = s.reason if not stale else "sync_stale"
            snap[anchor_id] = SyncStatus(
                anchor_id=anchor_id,
                last_update_s=s.last_update_s,
                quality=s.quality,
                healthy=healthy,
                reason=reason,
            )
        return snap
