from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from .models import FusedState, TeamMetrics


class NdjsonSink:
    """Append-only sink for demo artifacts.

    This format is intentionally boring: it is easy to tail, diff, replay, and ingest into
    Kafka, ClickHouse, or DuckDB-based validation notebooks later.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("w", encoding="utf-8")

    def write_state(self, s: FusedState) -> None:
        rec = {"kind": "player_state", **asdict(s)}
        self._fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def write_team_metrics(self, m: TeamMetrics) -> None:
        rec = {"kind": "team_metrics", **asdict(m)}
        self._fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def close(self) -> None:
        self._fh.close()

    def __enter__(self) -> "NdjsonSink":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
