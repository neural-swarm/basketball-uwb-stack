from tracking_mvp.config import DemoConfig
from tracking_mvp.main import run_demo


def test_demo_runs_and_produces_team_frames():
    cfg = DemoConfig(players_on_court=4)
    cfg.timing.duration_s = 2.0
    cfg.output.write_ndjson = False
    summary = run_demo(cfg)
    assert summary["team_frames"] > 0
    assert summary["stream_events"] > 0
    assert len(summary["players"]) == 4
