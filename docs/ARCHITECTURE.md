# Basketball UWB/LPS Tracking Stack
English | [Русский](ARCHITECTURE_ru.md)

## 1. Purpose

This document defines the engineering boundaries, expected performance, limitations, and validation criteria for an MVP basketball player tracking system based on indoor positioning (LPS/UWB) with optional IMU fusion.

The goal is to build a system suitable for:

* spatial player analytics,
* movement/load analytics,
* backend and event-pipeline development,
* controlled scalability testing in a real indoor arena.

---

## 2. Scope

* Player tracking (on-court)
* Spatial analytics (heatmaps, spacing, trajectories)
* Movement analytics (speed, acceleration, workload)
* LPS-only mode
* IMU-only mode
* LPS+IMU fusion mode (advanced)
* Ball tracking

---

## 3. Tracking Modes

## 3.1 LPS-only

**Use case:** spatial analytics and positional backbone.

Provides:

* Player XY position
* Trajectories
* Heatmaps
* Spacing metrics
* Distance traveled
* Speed (derived from coordinates)
* Acceleration (derived from coordinates)

Limitations:

* Weaker vertical (Z) accuracy
* Sensitivity to anchor geometry and RF conditions
* Near-line decisions are probabilistic, not adjudication-grade

---

## 3.2 IMU-only

**Use case:** movement/load analytics and biomechanics-adjacent metrics.

Provides:

* Acceleration/deceleration profiles
* Direction-change events
* Jump detection (timing/relative dynamics)
* Workload metrics

Limitations:

* No absolute on-court position
* No spacing/heatmaps
* Drift when integrating into position without external correction

---

## 3.3 LPS + IMU Fusion (advanced)

**Use case:** improved stability and extended analytics.

Provides:

* Smoother trajectories
* Reduced jitter
* Better resilience to short RF dropouts
* Higher-quality jump features
* Improved event detection quality

Limitations:

* Increased system complexity
* Stricter synchronization requirements
* Does not automatically provide referee-grade line-call accuracy

---

## 4. Target System Parameters (Basketball MVP)

Target conditions (approximate):

* Venue: standard indoor basketball court
* Actively tracked players: up to 10 on court
* Number of anchors: 6–8
* Tracking mode: TDoA preferred for scalability

### 4.1 Target Metrics

* **Update rate:** 20 Hz per player (target)
* **End-to-end latency:** < 80 ms (P95)
* **XY error (median):** 10–20 cm
* **XY error (P95):** < 40 cm
* **Stable operation in dense player clusters**
* **Graceful degradation under RF/channel load**

> These are engineering target values, not vendor guarantees.

---

## 5. What Determines Accuracy

Accuracy is a function of system architecture and environment, not a single device parameter.

### 5.1 Key Factors

* **Anchor geometry** (most critical factor)
* **Anchor installation height** (recommended: 5–8 m)
* **Number of anchors** (recommended: 6–8)
* **Anchor synchronization stability**
* **RF environment** (metal structures, reflections, body shadowing)
* **Number of active tags**
* **Tracking mode** (TDoA vs TWR)
* **Filtering strategy** (e.g., Kalman/EKF/UKF)
* **Calibration quality**

---

## 6. Calibration

Calibration ensures alignment between anchor time synchronization, spatial geometry, and the physical markings of the basketball court.

All anchors must operate within a single stable time reference. Drift or loss of synchronization directly degrades positioning accuracy and increases jitter.

---

## 7. Frequency, Stability, and Scaling

As the number of active tags increases, the system may experience:

* reduced effective update rate per player,
* increased latency,
* increased jitter,
* higher packet loss,
* degradation of practical trajectory quality.

---

## 8. Ball Tracking

Compared to player tracking, ball tracking requires:

* higher update rate (target ≥50 Hz),
* minimal latency,
* robustness to short signal dropouts,
* stable operation during rapid direction changes and rotation.

For this reason, ball tracking is considered an advanced system component and is not included in the base implementation.

Ball tracking uses a dedicated hardware configuration different from standard player tags.

**Embedded ball tag**

* Compact UWB module integrated inside the ball,
* Support for high update rate,
* Impact-resistant housing,
* Optimized antenna configuration accounting for ball rotation.

---

## 9. What This System Is NOT

* a referee-grade line-call system,
* a system with guaranteed centimeter-level accuracy under all conditions,
* a full broadcast production tracking pipeline,
* a replacement for multi-camera optical tracking in high-end TV workflows.
