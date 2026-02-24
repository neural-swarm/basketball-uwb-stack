from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class AffineClockMapper:
    """Incrementally maps source clock to edge clock using affine fit.

    We keep a lightweight online estimate. It is intentionally simple, but structured so it
    can be replaced by a proper synchronization module (PTP diagnostics, anchor sync health,
    cross-correlation, etc.) without changing the tracker business logic.
    """

    alpha: float = 0.02
    slope: float = 1.0
    offset_ns: float = 0.0
    initialized: bool = False

    def observe(self, source_ts_ns: int, ingest_ts_ns: int) -> None:
        if not self.initialized:
            self.offset_ns = float(ingest_ts_ns - source_ts_ns)
            self.slope = 1.0
            self.initialized = True
            return

        # Predict edge time from source clock and compute residual.
        pred = self.map_ts(source_ts_ns)
        residual = float(ingest_ts_ns - pred)

        # Offset tracks short-term latency / clock alignment drift.
        self.offset_ns += self.alpha * residual

        # Slope tracks clock skew. We update conservatively to avoid overfitting jitter.
        centered_source = max(float(source_ts_ns), 1.0)
        self.slope += (self.alpha * 1e-12) * residual / centered_source

    def map_ts(self, source_ts_ns: int) -> int:
        return int(self.slope * float(source_ts_ns) + self.offset_ns)
