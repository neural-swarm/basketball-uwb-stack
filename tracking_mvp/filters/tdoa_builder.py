from __future__ import annotations

from dataclasses import dataclass

from .types import AnchorReception, TdoaObservation

SPEED_OF_LIGHT_MPS = 299_792_458.0


@dataclass(slots=True)
class TdoaBuilder:
    """Build TDoA observations from synchronized anchor receptions.

    The builder assumes all receptions in one batch correspond to the same tag frame, or at least can
    be grouped by `(tag_id, frame_id)`. This keeps the code tutorial-friendly and easy to reuse in a
    streaming aggregator.
    """

    min_anchors_per_frame: int = 4
    reference_policy: str = "earliest"  # "earliest" or "best_quality"

    def build_many(self, receptions: list[AnchorReception]) -> list[TdoaObservation]:
        groups: dict[tuple[str, int], list[AnchorReception]] = {}
        for rx in receptions:
            groups.setdefault((rx.tag_id, rx.frame_id), []).append(rx)

        out: list[TdoaObservation] = []
        for (_, _), batch in groups.items():
            obs = self.build_one(batch)
            if obs is not None:
                out.append(obs)
        return out

    def build_one(self, receptions: list[AnchorReception]) -> TdoaObservation | None:
        if len(receptions) < self.min_anchors_per_frame:
            return None

        # Choose a reference anchor. Earliest timestamp is a common and intuitive default.
        ref = self._choose_reference(receptions)
        if ref is None:
            return None

        delta_range_m: dict[str, float] = {}
        weights: dict[str, float] = {}
        for rx in receptions:
            if rx.anchor_id == ref.anchor_id:
                continue
            dt_s = rx.rx_time_s - ref.rx_time_s
            delta_range_m[rx.anchor_id] = dt_s * SPEED_OF_LIGHT_MPS
            weights[rx.anchor_id] = self._weight_from_reception(rx)

        if len(delta_range_m) < (self.min_anchors_per_frame - 1):
            return None

        return TdoaObservation(
            tag_id=ref.tag_id,
            frame_id=ref.frame_id,
            t_ref_s=ref.rx_time_s,
            ref_anchor_id=ref.anchor_id,
            delta_range_m=delta_range_m,
            weights=weights,
            metadata={"n_receptions": float(len(receptions))},
        )

    def _choose_reference(self, receptions: list[AnchorReception]) -> AnchorReception | None:
        if not receptions:
            return None
        if self.reference_policy == "best_quality":
            return max(receptions, key=self._quality_score)
        return min(receptions, key=lambda r: r.rx_time_s)

    def _quality_score(self, rx: AnchorReception) -> float:
        score = 0.0
        if rx.fp_power_dbm is not None:
            score += rx.fp_power_dbm
        if rx.rssi_dbm is not None:
            score += 0.2 * rx.rssi_dbm
        if rx.sync_quality is not None:
            score += 10.0 * rx.sync_quality
        return score

    def _weight_from_reception(self, rx: AnchorReception) -> float:
        # The exact mapping is hardware/vendor specific. This tutorial version only demonstrates the seam.
        weight = 1.0
        if rx.sync_quality is not None:
            weight *= max(0.1, rx.sync_quality)
        if rx.fp_power_dbm is not None:
            weight *= max(0.2, min(2.0, (rx.fp_power_dbm + 100.0) / 20.0))
        if "suspect_nlos" in rx.flags:
            weight *= 0.25
        return max(1e-3, weight)
