# Використання ШІ: Codex додав порівняння CI та GHCR. Перевірка: pytest і Ruff.
# Codex прибрав довільний шлях --markdown (S8707). Перевірка: регресійний тест CLI та SonarCloud у PR.
"""Compare Lab 10 deployment definitions over the same CI cohort."""

import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlencode

from scripts.ci_metrics import calculate, collect, contains_commit, github, measure, timestamp


def comparison_table(report):
    def duration(stats):
        if stats["count"] == 0:
            return "Немає спостережень"
        return f"{stats['mean_seconds']:.2f} / {stats['median_seconds']:.2f} с"

    def percent(value):
        return "Немає спостережень" if value is None else f"{value:.2f}%"

    ci, ghcr = report["ci"], report["ghcr"]
    return "\n".join([
        "# Порівняння визначень розгортання",
        f"\nПеріод: {report['from']} — {report['to_exclusive']} (верхня межа виключна).",
        f"\nПовна вибірка: {report['complete_comparison']}. "
        f"Без завершеної публікації: {report['pending_publication_ci_ids']}.",
        "\n| Метрика | Зелений CI | Публікація GHCR |",
        "| --- | --- | --- |",
        f"| Розгортань / тиждень | {ci['deployments_per_week']:.2f} | {ghcr['deployments_per_week']:.2f} |",
        f"| Час змін: середнє / медіана | {duration(ci['lead_time'])} | {duration(ghcr['lead_time'])} |",
        f"| Частота збоїв | {percent(ci['change_failure_percent'])} | "
        f"{percent(ghcr['change_failure_percent'])} |",
        f"| Відновлення: середнє / медіана | {duration(ci['recovery_time'])} | "
        f"{duration(ghcr['recovery_time'])} |",
        "\nМетодика й обмеження: [container-release.md](container-release.md).",
        "\n## Використання ШІ",
        "Таблицю створено скриптом Codex; алгоритм перевірено pytest. Джерело — JSON цього запуску.",
        "",
    ])


def publication_rows(ci_rows, publications, end):
    """Join by source CI ID, never by workflow_run's potentially newer head SHA."""
    indexed = {}
    for publication in publications:
        match = re.fullmatch(r"Publish ([0-9a-f]{40}) CI (\d+)", publication["display_title"])
        if match:
            indexed.setdefault(int(match[2]), []).append((match[1], publication))
    rows, pending = [], []
    for source in ci_rows:
        if source["conclusion"] == "failure":
            rows.append(dict(source))
            continue
        if source["conclusion"] != "success":
            continue
        candidates = indexed.get(source["id"], [])
        candidates = [
            run for sha, run in candidates
            if sha == source["sha"] and run["status"] == "completed"
            and run["conclusion"] in {"success", "failure"}
            and timestamp(run["updated_at"]) < end
        ]
        if not candidates:
            pending.append(source["id"])
            continue
        publication = max(candidates, key=lambda run: (run["run_attempt"], run["id"]))
        completed = timestamp(publication["updated_at"])
        if completed < source["completed_at"]:
            raise ValueError("Publication precedes source CI completion")
        rows.append({
            **source,
            "conclusion": publication["conclusion"],
            "completed_at": completed,
            "publication_run_id": publication["id"],
            "publication_url": publication["html_url"],
        })
    return rows, pending


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--from", dest="start", required=True)
    parser.add_argument("--to", dest="end", required=True)
    parser.add_argument("--markdown", action="store_true", help="also write docs/ci-cd/container-comparison.md")
    args = parser.parse_args()
    start, end = timestamp(args.start), timestamp(args.end)
    if start >= end:
        parser.error("--from must precede --to")
    runs = collect(args.repo, "ci.yaml", start, end)
    with ThreadPoolExecutor(max_workers=5) as pool:
        rows = list(pool.map(lambda run: measure(run, args.repo), runs))
    query = urlencode({"event": "workflow_run", "per_page": 100})
    pages = github(f"repos/{args.repo}/actions/workflows/publish-container.yml/runs?{query}", paginate=True)
    publications = [run for page in pages for run in page["workflow_runs"]]
    delivered, pending = publication_rows(rows, publications, end)

    def contains(base, head):
        return contains_commit(args.repo, base, head)

    report = {
        "repository": args.repo,
        "from": start.isoformat(),
        "to_exclusive": end.isoformat(),
        "ci": calculate(rows, start, end, contains),
        "ghcr": calculate(delivered, start, end, contains),
        "pending_publication_ci_ids": pending,
        "publication_evidence": publications,
        "complete_comparison": bool(rows) and not pending,
        "Використання ШІ": "Codex підготував підрахунок; алгоритм перевірено pytest.",
    }
    # Only the four metrics are comparable here: publication job intervals are not collected.
    for key in (
        "queue_seconds", "execution_seconds", "other_seconds",
        "queue_percent_of_lead_time", "execution_percent_of_lead_time",
    ):
        report["ghcr"].pop(key)
    for change in report["ghcr"]["lead_time_changes"]:
        for key in ("queue_seconds", "execution_seconds", "other_seconds"):
            change.pop(key)
    if args.markdown:
        destination = Path(__file__).resolve().parents[1] / "docs/ci-cd/container-comparison.md"
        destination.write_text(comparison_table(report), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
