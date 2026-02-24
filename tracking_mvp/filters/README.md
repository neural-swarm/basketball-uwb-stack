# Filters / Positioning Tutorial Pipeline (UWB TDoA)
English | [Русский](README_ru.md)

This is a layer between the stream of raw anchor distance measurements and the final user trajectory.

The idea is simple: in the original scaffold we already had a `sensor_fusion` layer that worked with ready‑made coordinates. Here we demonstrate what the path looks like before that point, when we start from UWB anchors and TDoA.

Important: this is not production code. It is a set of transparent modules that demonstrate the processing sequence, responsibility boundaries, and the exact places where a production implementation would later be inserted.

---

## Input Data and Infrastructure

We assume that anchors (for example, **UbiTrack-A1**) are deployed on the court and are already capable of operating in a network and participating in inter‑anchor time synchronization within their platform. For us, this becomes a practical assumption: timestamps coming from anchors can be brought into a common time scale (or are already sufficiently close to one).

In other words, this project does not implement low‑level firmware synchronization. We start from the point where:

* anchor receptions are already available on Ubuntu/edge,
* each reception has `anchor_id`, `frame_id`, `tag_id`, `rx_time_s`,
* and at least minimal quality fields (RSSI / first‑path / flags) are provided if the hardware exposes them.

---

## Processing Sequence

### 1. `anchor_sync_adapter.py`

This is not anchor synchronization itself, but an adapter for synchronization assumptions. It maintains per‑anchor state (how fresh the synchronization is, what quality score was reported from the lower layer, whether the anchor should be temporarily excluded from calculations).

Why it exists: even if synchronization is provided out of the box, the upper pipeline benefits from having an explicit layer that can decide whether a specific anchor should be used at a given moment.

---

### 2. `tdoa_builder.py`

Builds a TDoA measurement for a single UWB frame/tag from raw reception events (`AnchorReception`):

* groups receptions by `(tag_id, frame_id)`,
* selects a reference anchor,
* computes time‑of‑arrival differences,
* converts them into distance differences (`Δr = c * Δt`).

The output is a structured measurement suitable for multilateration.

---

### 3. `multilateration.py`

Solves the inverse problem: given a set of TDoA measurements (distance differences to anchors), estimate position `(x, y)`.

The implementation here uses a tutorial‑level weighted Gauss‑Newton approach. It demonstrates:

* how residuals are formed,
* how to use a tracker prior (prediction) as the initial guess,
* how measurement weights are applied,
* how to obtain a rough covariance / residual quality estimate.

---

### 4. `quality_filters.py`

This is the validation layer:

* drops obviously bad receptions,
* flags likely NLOS cases using simple heuristics,
* performs gating based on speed constraints or Mahalanobis distance relative to the predicted state.

In production systems this layer typically grows the most. Here it is intentionally simple but shows the correct architectural placement.

---

### 5. `kf_core.py`

A generic linear Kalman core (`predict` / `update`) with no knowledge of UWB, IMU, or sports logic. It is used both by the tutorial `kalman_tracker.py` and the upper‑level module `tracking_mvp/sensor_fusion.py`, avoiding duplication of mathematical logic.

---

### 6. `kalman_tracker.py`

A basic 2D CV (constant velocity) Kalman tracker:

* consumes position measurements after multilateration,
* performs predict/update,
* supports measurement covariance,
* operates as a stateful streaming component.

This layer deals with trajectory estimation rather than raw radio localization.

---

### 7. `imm_tracker.py`

A tutorial IMM implementation built on top of multiple Kalman models.

It is intentionally kept transparent: several filters with different process noise intensities, Bayesian model probability updates, and state mixing.

---

## How This Connects to the Main Scaffold

The processing chain can now be viewed as:

`anchor RX -> sync adapter -> TDoA builder -> multilateration -> quality filters -> Kalman/IMM -> analytics`

---

## What Must Be Strengthened for Real Use

This folder intentionally includes simplifications:

* 2D model only, without detailed height modeling or body/tag geometry,
* simple NLOS heuristics instead of a full measurement quality model,
* simplified covariance estimation,
* minimal IMM without advanced motion modes,
* no multi‑target association.

However, as an engineering baseline, this is already solid: the code can be read, executed on synthetic data, and each module can be replaced independently with a production implementation.
