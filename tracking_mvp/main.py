from __future__ import annotations

from dataclasses import asdict
import argparse
import json

from .config import DemoConfig
from .pipeline import TrackingEngine
from .simulation import DemoStreamFactory


def run_demo(cfg: DemoConfig | None = None, mode: str = "lps") -> dict[str, object]:
    """Run one end-to-end demo.

    Modes:
      - lps: baseline tutorial (simulated LPS + IMU)
      - tdoa: demonstrate `tracking_mvp.filters` pipeline feeding the existing fusion stack
    """
    cfg = cfg or DemoConfig()
    stream = DemoStreamFactory(cfg)
    if mode == "tdoa":
        events = stream.generate_tdoa_positions()
    else:
        events = stream.generate()

    engine = TrackingEngine(cfg)
    engine.run(events)
    return engine.summarize()


def _json_default(obj):
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    raise TypeError(type(obj).__name__)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="tracking_mvp", add_help=True)
    parser.add_argument(
        "--mode",
        choices=["lps", "tdoa"],
        default="lps",
        help="Which tutorial pipeline to run: baseline LPS+IMU or TDoA-derived positioning + IMU.",
    )
    args = parser.parse_args(argv)

    summary = run_demo(mode=args.mode)
    print(json.dumps(summary, default=_json_default, indent=2))


if __name__ == "__main__":
    main()
