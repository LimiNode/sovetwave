#!/usr/bin/env python3
"""Build a redacted, reproducible review bundle from behavioral-eval runs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import statistics
import zipfile
from datetime import UTC, datetime
from pathlib import Path


TOKEN_RE = re.compile(r"tokens used[ \t]*\r?\n[ \t]*([0-9 ,\u00a0\u202f]+)", re.IGNORECASE)
MODEL_RE = re.compile(r"(?:^|\n)model:\s*([^\s\r\n]+)", re.IGNORECASE)
CODEX_USAGE_COMPONENTS = (
    "input_tokens",
    "cached_input_tokens",
    "cache_write_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
)


def parse_tokens(stderr: str) -> int | None:
    match = TOKEN_RE.search(stderr or "")
    if not match:
        return None
    digits = re.sub(r"\D", "", match.group(1))
    return int(digits) if digits else None


def parse_model(stderr: str) -> str | None:
    match = MODEL_RE.search(stderr or "")
    return match.group(1) if match else None


def load_run(path: Path) -> dict:
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return {"partial": True, "results": rows}


def sanitize_result(experiment: str, revision: str, row: dict) -> dict:
    stderr = row.get("stderr") or ""
    process_status = row.get("process_status", row.get("status"))
    # Missing telemetry in legacy observations remains unknown.  In particular,
    # do not turn an absent dirty-tree flag into a claim that the tree was clean.
    reported_tokens = row.get("reported_tokens")
    if reported_tokens is None:
        reported_tokens = parse_tokens(stderr)
    observed_revision = row.get("skill_revision")
    if observed_revision is not None:
        if not isinstance(observed_revision, str) or not observed_revision:
            raise ValueError(f"invalid skill_revision in observation: {observed_revision!r}")
        # Operators commonly pass a short SHA in --run; accept it only when
        # the recorded full revision has that prefix.
        if not (observed_revision == revision or observed_revision.startswith(revision)):
            raise ValueError(
                f"observation skill_revision {observed_revision!r} does not match supplied revision {revision!r}"
            )
    codex_usage = row.get("codex_usage")
    usage_events = row.get("codex_usage_events")
    duplicate_usage_events = row.get("codex_duplicate_usage_events")
    # Structured usage is safe to flatten only when exactly one aggregate
    # turn snapshot was observed.  Missing legacy metadata stays unknown.
    usage_valid = (
        isinstance(codex_usage, dict)
        and usage_events == 1
        and duplicate_usage_events == 0
    )
    usage_fields = {
        f"codex_{component}": codex_usage.get(component) if usage_valid else None
        for component in CODEX_USAGE_COMPONENTS
    }
    return {
        "experiment": experiment,
        "revision": revision,
        "case_id": row.get("case_id"),
        "variant": row.get("variant"),
        "repetition": row.get("repetition"),
        "sequence": row.get("sequence"),
        "activation": row.get("activation"),
        "execution_mode": row.get("execution_mode"),
        "prompt": row.get("prompt"),
        "assertions": row.get("assertions") or [],
        "applicable_axes": row.get("applicable_axes"),
        "capability_stage": row.get("capability_stage"),
        "process_status": process_status,
        "semantic_status": row.get("semantic_status"),
        "semantic_class": row.get("semantic_class"),
        "requested_model": row.get("requested_model"),
        "resolved_model": row.get("resolved_model") or parse_model(stderr),
        "reported_tokens": reported_tokens,
        "elapsed_seconds": row.get("elapsed_seconds"),
        "skill_revision": observed_revision,
        "material_inputs_dirty": row.get("material_inputs_dirty"),
        "attempt": row.get("attempt"),
        "recovered": row.get("recovered"),
        "original_process_status": row.get("original_process_status"),
        "codex_usage": codex_usage,
        "codex_usage_status": row.get("codex_usage_status"),
        "codex_usage_events": usage_events,
        "codex_duplicate_usage_events": duplicate_usage_events,
        "codex_event_types": row.get("codex_event_types"),
        "codex_tool_calls": row.get("codex_tool_calls"),
        "codex_anonymous_tool_items": row.get("codex_anonymous_tool_items"),
        "codex_item_counts_by_type": row.get("codex_item_counts_by_type"),
        "reference_trace_status": row.get("reference_trace_status"),
        "reference_files_read": row.get("reference_files_read") or [],
        "response": row.get("response") or "",
        **usage_fields,
    }


def statistics_rows(observations: list[dict]) -> list[dict]:
    groups: dict[tuple[str, str, str], list[dict]] = {}
    for row in observations:
        key = (row["experiment"], row["revision"], row["variant"])
        groups.setdefault(key, []).append(row)
    output: list[dict] = []
    for (experiment, revision, variant), rows in sorted(groups.items()):
        completed = [row for row in rows if row["process_status"] == "completed"]
        tokens = [row["reported_tokens"] for row in completed if isinstance(row["reported_tokens"], int)]
        elapsed_completed = [
            row["elapsed_seconds"] for row in completed
            if isinstance(row["elapsed_seconds"], (int, float))
        ]
        elapsed_all = [
            row["elapsed_seconds"] for row in rows
            if isinstance(row["elapsed_seconds"], (int, float))
        ]
        usage_totals: dict[str, int] = {}
        usage_values: dict[str, list[int]] = {component: [] for component in CODEX_USAGE_COMPONENTS}
        for row in completed:
            usage = row.get("codex_usage")
            if not (
                isinstance(usage, dict)
                and row.get("codex_usage_events") == 1
                and row.get("codex_duplicate_usage_events") == 0
            ):
                continue
            for component in CODEX_USAGE_COMPONENTS:
                value = usage.get(component)
                if isinstance(value, int) and not isinstance(value, bool):
                    usage_totals[component] = usage_totals.get(component, 0) + value
                    usage_values[component].append(value)
        stats_row = {
            "experiment": experiment,
            "revision": revision,
            "variant": variant,
            "observations": len(rows),
            "completed": len(completed),
            "timeouts": sum(row["process_status"] == "timeout" for row in rows),
            "failures": sum(row["process_status"] in {"failed", "invalid_empty_response"} for row in rows),
            "token_observations_completed": len(tokens),
            "tokens_mean_completed": round(statistics.mean(tokens), 2) if tokens else None,
            "tokens_median_completed": round(statistics.median(tokens), 2) if tokens else None,
            "tokens_min_completed": min(tokens) if tokens else None,
            "tokens_max_completed": max(tokens) if tokens else None,
            "elapsed_mean_completed_seconds": round(statistics.mean(elapsed_completed), 3) if elapsed_completed else None,
            "elapsed_observations_all": len(elapsed_all),
            "elapsed_mean_all_seconds": round(statistics.mean(elapsed_all), 3) if elapsed_all else None,
            "codex_usage_totals_completed": json.dumps(usage_totals, sort_keys=True) if usage_totals else None,
            "reference_trace_observed": sum(row.get("reference_trace_status") == "observed" for row in rows),
        }
        for component, values in usage_values.items():
            stats_row[f"codex_{component}_observations_completed"] = len(values)
            stats_row[f"codex_{component}_mean_completed"] = round(statistics.mean(values), 2) if values else None
            stats_row[f"codex_{component}_median_completed"] = round(statistics.median(values), 2) if values else None
        output.append(stats_row)
    return output


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_spec(value: str) -> tuple[str, str, Path]:
    try:
        experiment, revision, source = value.split("=", 2)
    except ValueError as error:
        raise argparse.ArgumentTypeError("run must have EXPERIMENT=REVISION=PATH form") from error
    if not experiment or not revision or not source:
        raise argparse.ArgumentTypeError("run must have EXPERIMENT=REVISION=PATH form")
    return experiment, revision, Path(source)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run", action="append", type=parse_spec, required=True,
                        help="EXPERIMENT=REVISION=PATH (repeat for each run)")
    args = parser.parse_args()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)

    observations: list[dict] = []
    runs: list[dict] = []
    for experiment, revision, source in args.run:
        run = load_run(source)
        rows = [sanitize_result(experiment, revision, row) for row in run.get("results", [])]
        observations.extend(rows)
        runs.append({
            "experiment": experiment,
            "revision": revision,
            "source_file": source.name,
            "partial": bool(run.get("partial", False)),
            "observations": len(rows),
            "cli_version": run.get("cli_version"),
            "variant_orders": run.get("variant_orders"),
            "order_balance": run.get("order_balance"),
            "provider": run.get("provider"),
            "material_inputs_dirty": run.get("material_inputs_dirty"),
            "skill_revision_dirty": run.get("skill_revision_dirty"),
            "dry_run": run.get("dry_run"),
        })

    stats = statistics_rows(observations)
    bundle = {
        "schema": "sovetwave-review-bundle-2",
        "created_at": datetime.now(UTC).isoformat(),
        "privacy": "command arrays and stderr were omitted; responses and non-secret telemetry were retained",
        "runs": runs,
        "statistics": stats,
        "observations": observations,
    }
    json_path = out / "review-bundle.json"
    json_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fields = [
        "experiment", "revision", "case_id", "variant", "repetition", "sequence",
        "execution_mode", "applicable_axes", "capability_stage",
        "process_status", "semantic_status", "semantic_class", "requested_model",
        "resolved_model", "reported_tokens", "elapsed_seconds", "skill_revision",
        "material_inputs_dirty", "attempt", "recovered", "original_process_status",
        "reference_trace_status", "codex_tool_calls", "codex_usage_events",
        "codex_duplicate_usage_events", "codex_usage_status",
        "codex_input_tokens", "codex_cached_input_tokens",
        "codex_cache_write_input_tokens", "codex_output_tokens",
        "codex_reasoning_output_tokens", "codex_anonymous_tool_items",
    ]
    csv_observations = []
    for row in observations:
        csv_row = dict(row)
        if isinstance(csv_row.get("applicable_axes"), list):
            csv_row["applicable_axes"] = json.dumps(csv_row["applicable_axes"], ensure_ascii=False)
        csv_observations.append(csv_row)
    write_csv(out / "observations.csv", csv_observations, fields)
    write_csv(out / "statistics.csv", stats, list(stats[0]) if stats else [])

    response_lines = ["# Ответы live-проверки", ""]
    for row in observations:
        response_lines.extend([
            f"## {row['experiment']} — {row['case_id']} — {row['variant']} — repetition {row['repetition']}",
            "", f"- Process status: `{row['process_status']}`",
            f"- Attempt: `{row['attempt']}`; recovered: `{row['recovered']}`",
            f"- Reported tokens: `{row['reported_tokens']}`", "",
            "### Prompt", "", row["prompt"] or "", "", "### Assertions", "",
        ])
        response_lines.extend(f"- {assertion}" for assertion in row["assertions"])
        response_lines.extend(["", "### Response", "", row["response"], ""])
    responses_path = out / "responses.md"
    responses_path.write_text("\n".join(response_lines), encoding="utf-8")

    summary = out / "RESULTS-SUMMARY.md"
    summary_lines = [
        "# Сводка запусков", "", 
        "Это техническая сводка процесса. Семантические assertions не оценивались автоматически.", "",
        "| Experiment | Variant | Observations | Completed | Timeouts | Failures | Completed-token observations | Mean completed tokens | Mean completed elapsed (s) |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in stats:
        summary_lines.append(
            f"| {row['experiment']} | {row['variant']} | {row['observations']} | {row['completed']} | "
            f"{row['timeouts']} | {row['failures']} | {row['token_observations_completed']} | "
            f"{row['tokens_mean_completed']} | {row['elapsed_mean_completed_seconds']} |"
        )
    summary.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    readme = out / "README-for-review.md"
    readme.write_text(
        "# Пакет для независимого ревью\n\n"
        "Оцените каждый завершённый ответ по каждому assertion как `pass`, `partial` или `fail`; "
        "отдельно отметьте ложные утверждения и проверяет ли предложенная проверка именно заявленное свойство. "
        "Сначала сравните arms внутри одного эксперимента, затем повторения. Не выводите качество из длины ответа "
        "или числа токенов. `process_status` и семантическая оценка — разные измерения.\n\n"
        "Токены агрегированы только для `process_status=completed`; тайм-ауты и пропуски телеметрии считаются отдельно. "
        "Recovered-наблюдения не смешивайте с первыми попытками без отдельной оговорки. "
        "Поля `material_inputs_dirty`, `attempt`, `recovered` и `original_process_status` могут быть `null` в legacy-строках: "
        "это неизвестность, а не подтверждение чистого запуска.\n\n"
        "Проверьте `runs[].material_inputs_dirty` в `review-bundle.json`: если значение `true`, запуск "
        "начался при незакоммиченных материалах и не должен называться чистой репликацией без оговорки.\n\n"
        "Основные файлы: `review-bundle.json` (машинная структура), `observations.csv` (плоская таблица), "
        "`responses.md` (все prompt/assertions/ответы), `statistics.csv` и `RESULTS-SUMMARY.md`. "
        "Сверяйте целостность по `SHA256SUMS.txt`.\n",
        encoding="utf-8",
    )
    deliverables = [summary, json_path, out / "observations.csv", out / "statistics.csv", responses_path, readme]
    sums_path = out / "SHA256SUMS.txt"
    sums_path.write_text("\n".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}" for p in deliverables) + "\n", encoding="ascii")
    deliverables.append(sums_path)
    zip_path = out / "sovetwave-review-bundle.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in deliverables:
            archive.write(path, arcname=path.name)
    print(zip_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
