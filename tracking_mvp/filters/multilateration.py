from __future__ import annotations

from dataclasses import dataclass
from math import hypot

from .types import AnchorSpec, PositionEstimate, PredictedState, TdoaObservation


@dataclass(slots=True)
class TdoaMultilateration2D:
    """Weighted Gauss-Newton multilateration for 2D TDoA.

    The solver uses a reference anchor and solves hyperbolic residual equations:
    ||p-ai|| - ||p-a_ref|| = delta_range_i

    This implementation is intentionally compact and explicit so the algorithm is easy to inspect.
    """

    max_iters: int = 12
    step_tol_m: float = 1e-4
    residual_tol_m: float = 1e-3
    damping: float = 1e-6

    def solve(
        self,
        obs: TdoaObservation,
        anchors: dict[str, AnchorSpec],
        prior: PredictedState | None = None,
    ) -> PositionEstimate | None:
        ref = anchors.get(obs.ref_anchor_id)
        if ref is None:
            return None

        used_anchor_ids = [obs.ref_anchor_id]
        equations: list[tuple[AnchorSpec, float, float]] = []
        for anchor_id, delta_range_m in obs.delta_range_m.items():
            a = anchors.get(anchor_id)
            if a is None:
                continue
            w = max(1e-6, obs.weights.get(anchor_id, 1.0))
            equations.append((a, delta_range_m, w))
            used_anchor_ids.append(anchor_id)

        # TDoA in 2D typically needs at least 3 equations + a reference anchor (4 anchors total).
        if len(equations) < 3:
            return None

        x, y = self._initial_guess(ref, equations, prior)
        prev_residual = float("inf")

        for _ in range(self.max_iters):
            h11 = self.damping
            h12 = 0.0
            h22 = self.damping
            g1 = 0.0
            g2 = 0.0
            residual_sq_sum = 0.0
            weight_sum = 0.0

            r0 = max(hypot(x - ref.x_m, y - ref.y_m), 1e-6)
            d0x = (x - ref.x_m) / r0
            d0y = (y - ref.y_m) / r0

            for anchor, delta_range_m, w in equations:
                ri = max(hypot(x - anchor.x_m, y - anchor.y_m), 1e-6)
                dix = (x - anchor.x_m) / ri
                diy = (y - anchor.y_m) / ri

                model = ri - r0
                residual = model - delta_range_m
                jx = dix - d0x
                jy = diy - d0y

                # Weighted normal equations: H dx = -g, where H = J'WJ and g = J'Wr.
                h11 += w * jx * jx
                h12 += w * jx * jy
                h22 += w * jy * jy
                g1 += w * jx * residual
                g2 += w * jy * residual
                residual_sq_sum += w * residual * residual
                weight_sum += w

            det = h11 * h22 - h12 * h12
            if abs(det) < 1e-12:
                break

            inv11 = h22 / det
            inv12 = -h12 / det
            inv22 = h11 / det

            dx = -(inv11 * g1 + inv12 * g2)
            dy = -(inv12 * g1 + inv22 * g2)

            x += dx
            y += dy

            residual_rms_m = (residual_sq_sum / max(weight_sum, 1e-9)) ** 0.5
            step_norm = hypot(dx, dy)
            if step_norm < self.step_tol_m:
                break
            if abs(prev_residual - residual_rms_m) < self.residual_tol_m:
                break
            prev_residual = residual_rms_m

        cov = self._covariance_from_hessian(h11, h12, h22)
        residual_rms_m = self._final_residual_rms(x, y, ref, equations)

        return PositionEstimate(
            tag_id=obs.tag_id,
            frame_id=obs.frame_id,
            t_s=obs.t_ref_s,
            x_m=x,
            y_m=y,
            residual_rms_m=residual_rms_m,
            covariance_xy=cov,
            used_anchor_ids=tuple(used_anchor_ids),
            debug={"n_eq": float(len(equations))},
        )

    def _initial_guess(
        self,
        ref: AnchorSpec,
        equations: list[tuple[AnchorSpec, float, float]],
        prior: PredictedState | None,
    ) -> tuple[float, float]:
        if prior is not None:
            return prior.x_m, prior.y_m

        # Fallback: centroid of participating anchors. Good enough for a tutorial initialization.
        xs = [ref.x_m] + [a.x_m for a, _, _ in equations]
        ys = [ref.y_m] + [a.y_m for a, _, _ in equations]
        return sum(xs) / len(xs), sum(ys) / len(ys)

    def _covariance_from_hessian(
        self, h11: float, h12: float, h22: float
    ) -> tuple[tuple[float, float], tuple[float, float]]:
        det = h11 * h22 - h12 * h12
        if abs(det) < 1e-12:
            return ((10.0, 0.0), (0.0, 10.0))
        inv11 = h22 / det
        inv12 = -h12 / det
        inv22 = h11 / det
        return ((inv11, inv12), (inv12, inv22))

    def _final_residual_rms(
        self,
        x: float,
        y: float,
        ref: AnchorSpec,
        equations: list[tuple[AnchorSpec, float, float]],
    ) -> float:
        r0 = max(hypot(x - ref.x_m, y - ref.y_m), 1e-6)
        total = 0.0
        wsum = 0.0
        for anchor, delta_range_m, w in equations:
            ri = max(hypot(x - anchor.x_m, y - anchor.y_m), 1e-6)
            residual = (ri - r0) - delta_range_m
            total += w * residual * residual
            wsum += w
        return (total / max(wsum, 1e-9)) ** 0.5
