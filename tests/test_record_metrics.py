"""The metrics recorder: one honest row per run, and it never breaks a build."""

import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "record_metrics.py"


def _load():
    spec = importlib.util.spec_from_file_location("record_metrics", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rm = _load()


def _item(tmp_path, name, theme, score):
    d = tmp_path / "_items"
    d.mkdir(exist_ok=True)
    (d / name).write_text(
        f'---\ntheme: {theme}\nscore: {score}\ntitle: "x"\n---\nbody\n',
        encoding="utf-8",
    )
    return d


def test_a_row_carries_the_funnel_the_distribution_and_the_themes(tmp_path):
    items = _item(tmp_path, "a.md", "reliability-assurance", "7.0")
    _item(tmp_path, "b.md", "business-markets", "8.0")
    health = {
        "totals": {"fetched": 114, "gated": 43, "published": 2,
                   "tokens": 227165,
                   "score_distribution": {"5": 3, "7": 30, "8": 10}},
        "errors": 0, "degraded": 1, "warnings": 12, "zero_sources": ["GDELT"],
    }
    row = rm.build_row(health, rm.published_items(items))

    assert row["funnel"] == {"fetched": 114, "gated": 43, "published": 2,
                             "tokens": 227165}
    assert row["score_distribution"] == {"5": 3, "7": 30, "8": 10}
    assert row["published_by_theme"] == {"reliability-assurance": 1,
                                         "business-markets": 1}
    assert row["published_scores"] == [7.0, 8.0]


def test_the_same_run_is_never_recorded_twice(tmp_path, monkeypatch, capsys):
    """A retried notify step must not double a day."""
    monkeypatch.setenv("GITHUB_RUN_ID", "42")
    series = tmp_path / "runs.json"
    health = tmp_path / "health.json"
    health.write_text(json.dumps({"totals": {"published": 1}}), encoding="utf-8")

    argv = ["record_metrics", "--health", str(health),
            "--items", str(tmp_path / "none"), "--series", str(series)]
    monkeypatch.setattr("sys.argv", argv)
    assert rm.main() == 0
    assert rm.main() == 0

    assert len(json.loads(series.read_text())) == 1


def test_a_corrupt_series_is_left_alone(tmp_path, monkeypatch):
    """Overwriting broken history would erase the evidence that it broke."""
    series = tmp_path / "runs.json"
    series.write_text("not json", encoding="utf-8")
    health = tmp_path / "health.json"
    health.write_text(json.dumps({"totals": {}}), encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["record_metrics", "--health", str(health),
                                     "--items", str(tmp_path / "none"),
                                     "--series", str(series)])
    assert rm.main() == 1
    assert series.read_text() == "not json"


def test_a_missing_health_summary_records_nothing_and_exits_green(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.argv", ["record_metrics",
                                     "--health", str(tmp_path / "absent.json"),
                                     "--items", str(tmp_path / "none"),
                                     "--series", str(tmp_path / "runs.json")])
    assert rm.main() == 0
    assert not (tmp_path / "runs.json").exists()


def test_schema_v2_items_carry_source_and_per_feed_rides_along(tmp_path):
    items = _item(tmp_path, "a.md", "practice", "7.0")
    (items / "a.md").write_text(
        '---\ntheme: practice\nscore: 7.0\nsource: "openai.com"\n---\nb\n',
        encoding="utf-8")
    health = {"totals": {"published": 1},
              "per_feed": {"OpenAI News": [3, False]}}

    row = rm.build_row(health, rm.published_items(items))

    assert row["items"] == [{"theme": "practice", "source": "openai.com",
                             "score": 7.0}]
    assert row["per_feed"] == {"OpenAI News": [3, False]}
