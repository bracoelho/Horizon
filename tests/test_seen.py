"""The seen store: novelty rather than recency (NEWS-Radar #91)."""
import json
import types
from datetime import date, timedelta

from src.seen import SeenStore


def _item(i):
    return types.SimpleNamespace(id=i)


def test_new_items_pass_and_recorded_ones_do_not(tmp_path):
    store = SeenStore(tmp_path / "seen.json")
    items = [_item("a"), _item("b")]
    assert len(store.filter_new(items)) == 2
    assert store.record(items) == 2
    assert store.filter_new(items) == []
    assert len(store.filter_new([_item("c")])) == 1


def test_it_survives_a_restart(tmp_path):
    path = tmp_path / "seen.json"
    first = SeenStore(path)
    first.record([_item("a")])
    first.save()
    assert SeenStore(path).filter_new([_item("a")]) == []


def test_a_corrupt_store_starts_empty_rather_than_stopping_the_run(tmp_path):
    path = tmp_path / "seen.json"
    path.write_text("{not json", encoding="utf-8")
    store = SeenStore(path)
    assert len(store) == 0
    assert len(store.filter_new([_item("a")])) == 1


def test_pruning_drops_only_what_is_older_than_the_window(tmp_path):
    path = tmp_path / "seen.json"
    old = (date.today() - timedelta(days=200)).isoformat()
    path.write_text(json.dumps({"old": old, "new": date.today().isoformat()}))
    store = SeenStore(path, keep_days=120)
    assert store.prune() == 1
    assert store.is_new("old")
    assert not store.is_new("new")
