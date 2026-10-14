"""Ядро бенча без сети и без базы: загрузка сценариев, разница состояний, проверки, сводка."""

import ast
import json
from pathlib import Path

import pytest

from evals.core import Checks, ScenarioError, diff, generic, judge, load, outcome
from evals.core.report import main, markdown, summarize, wilson

CORE = Path(__file__).parents[1] / "evals" / "core"
WORLDS = {"empty", "big"}


def _file(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "scenarios.toml"
    path.write_text(text)
    return path


GOOD = """
[[scenario]]
id = "hello"
split = "tune"
turns = ["привет"]
expect.asks = {}

[[scenario]]
id = "count"
split = "holdout"
world = "big"
tags = ["safety"]
turns = ["добавь", "ещё"]
expect.added = { collection = "items", count = 2 }
"""


def test_scenarios_load_from_toml(tmp_path):
    first, second = load(_file(tmp_path, GOOD), generic, WORLDS)
    assert (first.id, first.split, first.world, first.turns) == ("hello", "tune", "empty", ("привет",))
    assert (second.world, second.tags, second.expect) == ("big", ("safety",), {"added": {"collection": "items", "count": 2}})
    # Отпечаток зависит от слов и ожидания, а не от id.
    assert first.sha != second.sha
    assert load(_file(tmp_path, GOOD), generic, WORLDS)[0].sha == first.sha


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (('expect.asks = {}', 'expect.nope = {}'), "unknown check 'nope'"),
        (('expect.asks = {}', 'expect.asks = { loud = true }'), "unexpected keyword argument 'loud'"),
        (('expect.asks = {}', 'expect.added = { collection = "items" }'), "missing a required argument: 'count'"),
        (('split = "tune"', 'split = "train"'), "`split` must be one of"),
        (('turns = ["привет"]', 'turns = []'), "`turns` must be a non-empty list"),
        (('id = "hello"\n', 'id = "hello"\nworld = "moon"\n'), "unknown world 'moon'"),
        (('id = "hello"\n', 'id = "hello"\nnote = "x"\n'), "unknown keys ['note']"),
        (('id = "hello"', 'id = "count"'), "'count' appears twice"),
    ],
)
def test_a_broken_scenario_is_refused_at_load(tmp_path, change, message):
    old, new = change
    with pytest.raises(ScenarioError, match=message.replace("[", r"\[").replace("(", r"\(")):
        load(_file(tmp_path, GOOD.replace(old, new, 1)), generic, WORLDS)


def test_a_diff_shows_what_the_conversation_did():
    before = {"items": {"a": {"title": "A"}, "b": {"title": "B"}}, "pages": {}}
    after = {"items": {"a": {"title": "A2"}, "c": {"title": "C"}}, "pages": {}}
    found = diff(before, after)
    assert found.added == {"items": [{"id": "c", "title": "C"}]}
    assert found.removed == {"items": [{"id": "b", "title": "B"}]}
    assert found.changed == {"items": [({"id": "a", "title": "A"}, {"id": "a", "title": "A2"})]}
    assert sorted(found.touched("items")) == ["a", "b", "c"]
    assert found.touched("pages") == []


def test_generic_checks():
    before = {"items": {"a": {"t": 1}}, "pages": {"p": {"t": 1}}}
    after = {"items": {"a": {"t": 1}, "b": {"t": 2}}, "pages": {"p": {"t": 1}}}
    result = outcome(before, after, ("Записал. Во сколько?",))
    assert generic["untouched"](result, collections=["pages"]) is None
    assert generic["untouched"](result, collections=["items"]) == "touched {'items': ['b']}"
    assert generic["added"](result, collection="items", count=1) is None
    assert generic["added"](result, collection="items", count=2) == "items: added 1, want 2"
    assert generic["says"](result, words=["ЗАПИСАЛ", "во сколько"]) is None
    assert generic["says"](result, words=["завтра"]) == "the answer lacks ['завтра']"
    assert generic["asks"](result) is None


def test_judge_names_every_failed_check(tmp_path):
    scenario = load(_file(tmp_path, GOOD), generic, WORLDS)[1]
    nothing = outcome({}, {}, ("ок",))
    assert judge(scenario, generic, nothing) == ["added: items: added 0, want 2"]


def test_an_app_registry_extends_the_generic_one():
    mine = Checks(generic)

    @mine.register
    def calm(result) -> str | None:
        return None

    assert "calm" in mine and "asks" in mine and "calm" not in generic


@pytest.mark.parametrize(
    ("passed", "total", "low", "high"),
    [(8, 10, 0.490, 0.943), (10, 10, 0.722, 1.0), (0, 10, 0.0, 0.278), (65, 130, 0.415, 0.585)],
)
def test_wilson_interval(passed, total, low, high):
    found = wilson(passed, total)
    assert found == pytest.approx((low, high), abs=0.001)


def _row(run, scenario, ok, split="tune", seconds=2.0, reasons=None):
    return {
        "run": run, "scenario": scenario, "split": split, "ok": ok, "reasons": reasons or ([] if ok else ["x: bad"]),
        "chain": "google:m", "thinking": "low", "git": "abc", "prompt": "p1",
        "turns": [{"seconds": seconds, "input": 100, "cache_read": 50, "output": 10}],
    }


def test_summary_of_the_last_run():
    records = [_row("old", "a", False)] + [_row("new", "a", True)] * 3 + [
        _row("new", "b", True, "holdout"), _row("new", "b", False, "holdout", reasons=["moved: at 13:00"]),
    ]
    summary = summarize(records)
    assert summary.run == "new"
    assert {name: (t.passed, t.total) for name, t in summary.scenarios.items()} == {"a": (3, 3), "b": (1, 2)}
    assert {name: (t.passed, t.total) for name, t in summary.splits.items()} == {"holdout": (1, 2), "tune": (3, 3)}
    assert (summary.all_passed.passed, summary.all_passed.total) == (1, 2)
    assert summary.reasons == {"b": ["moved: at 13:00"]}
    assert summary.tokens == {"input": 500, "cache_read": 250, "output": 50}
    assert summary.seconds == 2.0
    assert summarize(records, "old").scenarios["a"].passed == 0


def test_a_collapse_is_marked_and_noise_is_not(tmp_path):
    then = [_row("base", "a", True)] * 10 + [_row("base", "b", True)] * 10
    now = [_row("now", "a", False)] * 8 + [_row("now", "a", True)] * 2 + [_row("now", "b", True)] * 9
    now += [_row("now", "b", False)]
    records = tmp_path / "bench.jsonl"
    records.write_text("".join(json.dumps(row) + "\n" for row in then + now))
    saved = tmp_path / "baseline.json"
    main([str(records), "--run", "base", "--save", str(saved)])
    table = markdown(summarize([*then, *now]), json.loads(saved.read_text()))
    assert "| a | tune | 2/10 [0.06–0.51] | ▼ was 10/10 |" in table
    assert "| b | tune | 9/10 [0.60–0.98] | was 10/10 |" in table


def test_the_core_knows_no_application():
    """Ядро переносится в другое приложение как есть: ни одного импорта almanac внутри."""
    for path in CORE.glob("*.py"):
        tree = ast.parse(path.read_text())
        names = [alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names]
        names += [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        assert not [name for name in names if name.split(".")[0] == "almanac"], path.name
