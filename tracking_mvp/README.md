# Basketball UWB/LPS Tracking
English | [Русский](README_ru.md)

This is an edge service for player tracking: it consumes a stream of sensor events (or their simulation), aligns timestamps to a common timescale, estimates motion state (position/velocity), computes basic analytics, and writes the resulting stream in a convenient format for replay and debugging.

The package is intentionally split into layers so that the simulator can later be replaced with real UWB/IMU adapters and the MVP can be gradually evolved into a production-grade system.

## Project Structure

### `main.py`

Entry point for application logic and CLI modes (`lps` / `tdoa`). This is where the event source is selected and the `TrackingEngine` is started.

### `models.py`

Domain types and data exchange contracts (`Envelope`, measurements, fused state, player and team metrics).

### `clocks.py`

Time alignment module between sensor sources and the edge host time. In the demo it is simple, but architecturally this is the place for offset/skew/drift compensation.

### `sensor_fusion.py`

Orchestrates sensor fusion around the Kalman model: IMU feeds the predict step, positional measurements feed the update step. The mathematical Kalman core is implemented in `filters/kf_core.py`, while this module handles sensor-specific logic and quality decisions.

### `analytics.py`

Streaming analytics on top of the estimated trajectory (speed, distance, per-player and team aggregates).

### `storage.py`

Output layer (sink) for writing states and metrics. Currently NDJSON for replay and debugging, but it can be replaced with Kafka/DB/WebSocket.

### `simulation.py`

Simulator of data sources for running the system without hardware. Supports both the basic path (LPS + IMU) and a demonstration TDoA path where positions first pass through `tracking_mvp/filters/`.

### `pipeline.py`

Builds the runtime pipeline: per-player trackers, clock alignment, sensor fusion, analytics, and periodic team metrics. This is the main orchestration layer that pushes the event stream through the system.

### `filters/`

Subpackage with RTLS pipeline modules: sync state adapter, TDoA builder, multilateration, quality gates, Kalman/IMM, and a shared Kalman core. See `filters/README.md` for the detailed processing sequence.
