"""Сводка прогона и сравнение с базовой линией.

    python -m evals.core.report bench.jsonl [--run ID] [--baseline FILE] [--save FILE]

Модель недетерминирована, поэтому итог сценария — `x/N` с 95% интервалом Уилсона, а не «прошёл».
При N=10 интервал на один сценарий широк: 8/10 — это примерно от 0.49 до 0.94. Поэтому решение
«стало хуже» принимают по сумме набора (`tune`, `holdout`), а по сценарию отмечают только обвал —
когда интервалы текущего прогона и базовой линии не пересекаются.
"""

import argparse
import json
import math
import statistics
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from evals.core.record import read

Z95 = 1.96


def wilson(passed: int, total: int, z: float = Z95) -> tuple[float, float]:
    """95% интервал доли успехов. Честнее нормального приближения на малых N и у краёв (0/N, N/N)."""
    if total == 0:
        return 0.0, 1.0
    rate = passed / total
    centre = (rate + z * z / (2 * total)) / (1 + z * z / total)
    spread = z * math.sqrt(rate * (1 - rate) / total + z * z / (4 * total * total)) / (1 + z * z / total)
    return max(0.0, centre - spread), min(1.0, centre + spread)


@dataclass(frozen=True)
class Tally:
    passed: int
    total: int

    @property
    def low(self) -> float:
        return wilson(self.passed, self.total)[0]

    @property
    def high(self) -> float:
        return wilson(self.passed, self.total)[1]

    def text(self) -> str:
        return f"{self.passed}/{self.total} [{self.low:.2f}–{self.high:.2f}]"


@dataclass(frozen=True)
class Summary:
    run: str
    meta: dict[str, list[str]]
    scenarios: dict[str, Tally]
    splits: dict[str, Tally]
    split_of: dict[str, str]
    # Доля сценариев, прошедших все N раз: для дела, на которое полагаются, важна она, а не средняя.
    all_passed: Tally
    seconds: float
    tokens: dict[str, int]
    reasons: dict[str, list[str]]


def summarize(records: list[dict[str, Any]], run: str | None = None) -> Summary:
    """Сводка одного прогона; без `run` — последнего в файле."""
    if not records:
        raise ValueError("no records")
    chosen = run or records[-1]["run"]
    rows = [row for row in records if row["run"] == chosen]
    if not rows:
        raise ValueError(f"no records of run {chosen!r}")
    by_case: dict[str, list[bool]] = defaultdict(list)
    split_of: dict[str, str] = {}
    reasons: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        by_case[row["scenario"]].append(bool(row["ok"]))
        split_of[row["scenario"]] = row["split"]
        if not row["ok"]:
            reasons[row["scenario"]].append(row.get("error") or "; ".join(row.get("reasons") or ["?"]))
    scenarios = {name: Tally(sum(oks), len(oks)) for name, oks in sorted(by_case.items())}
    splits = {
        split: Tally(sum(t.passed for n, t in scenarios.items() if split_of[n] == split),
                     sum(t.total for n, t in scenarios.items() if split_of[n] == split))
        for split in sorted(set(split_of.values()))
    }
    turns = [turn for row in rows for turn in row.get("turns", [])]
    conversations = [sum(turn["seconds"] for turn in row.get("turns", [])) for row in rows if row.get("turns")]
    tokens = {key: sum(turn.get(key, 0) for turn in turns) for key in ("input", "cache_read", "output")}
    meta = {key: sorted({str(row.get(key)) for row in rows}) for key in ("chain", "thinking", "git", "prompt")}
    return Summary(
        run=chosen, meta=meta, scenarios=scenarios, splits=splits, split_of=split_of,
        all_passed=Tally(sum(t.passed == t.total for t in scenarios.values()), len(scenarios)),
        seconds=statistics.median(conversations) if conversations else 0.0, tokens=tokens, reasons=dict(reasons),
    )


def baseline(summary: Summary) -> dict[str, Any]:
    """Принятая сводка для git: только итоги и то, что мерили, без следов и ответов."""
    return {
        "run": summary.run,
        "meta": summary.meta,
        "scenarios": {name: asdict(tally) for name, tally in summary.scenarios.items()},
        "splits": {name: asdict(tally) for name, tally in summary.splits.items()},
    }


def _shift(now: Tally, then: dict[str, int] | None) -> str:
    """▼ — интервалы разошлись вниз, ▲ — вверх; иначе разница в пределах шума и знака нет."""
    if then is None:
        return "new"
    old = Tally(then["passed"], then["total"])
    if now.high < old.low:
        return f"▼ was {old.passed}/{old.total}"
    if now.low > old.high:
        return f"▲ was {old.passed}/{old.total}"
    return f"was {old.passed}/{old.total}"


def markdown(summary: Summary, base: dict[str, Any] | None = None) -> str:
    lines = [f"# Bench run {summary.run}", ""]
    lines += [f"- {key}: {', '.join(values)}" for key, values in summary.meta.items()]
    if base is not None:
        lines.append(f"- baseline: run {base['run']}, prompt {', '.join(base['meta'].get('prompt', []))}")
    lines += ["", "| split | passed | vs baseline |", "|:--|:--|:--|"]
    for split, tally in summary.splits.items():
        then = base["splits"].get(split) if base else None
        lines.append(f"| {split} | {tally.text()} | {_shift(tally, then) if base else ''} |")
    lines += [
        "",
        (
            f"All N of N: {summary.all_passed.passed} of {summary.all_passed.total} scenarios. "
            f"Median conversation: {summary.seconds:.1f} s. "
            f"Tokens: input {summary.tokens['input']}, cached {summary.tokens['cache_read']}, "
            f"output {summary.tokens['output']}."
        ),
        "",
        "| scenario | split | passed | vs baseline | first failure |",
        "|:--|:--|:--|:--|:--|",
    ]
    for name, tally in summary.scenarios.items():
        then = base["scenarios"].get(name) if base else None
        failure = summary.reasons.get(name, [""])[0].replace("|", "\\|")[:120]
        shift = _shift(tally, then) if base else ""
        lines.append(f"| {name} | {summary.split_of[name]} | {tally.text()} | {shift} | {failure} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Summary of a bench run, compared with a baseline.")
    parser.add_argument("records", type=Path)
    parser.add_argument("--run", help="run id; the last run in the file by default")
    parser.add_argument("--baseline", type=Path, help="accepted summary to compare with")
    parser.add_argument("--save", type=Path, help="write this run as the new baseline")
    args = parser.parse_args(argv)
    summary = summarize(read(args.records), args.run)
    base = json.loads(args.baseline.read_text()) if args.baseline and args.baseline.exists() else None
    print(markdown(summary, base), end="")
    if args.save:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        args.save.write_text(json.dumps(baseline(summary), ensure_ascii=False, indent=1) + "\n")


if __name__ == "__main__":
    main()
