# Використання ШІ: Codex додав збір і підрахунок метрик.
# Перевірка: pytest і відтворення історичної вибірки GitHub Actions.
"""Reproduce the Lab 10 CI metrics from GitHub Actions."""

import argparse
import json
import subprocess  # nosec B404
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, median
from urllib.parse import quote, urlencode


def timestamp(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError(f"Expected a timestamp with a UTC offset: {value}")
    return parsed.astimezone(timezone.utc)


def github(endpoint, *, paginate=False):
    command = ["gh", "api", endpoint]
    if paginate:
        command.extend(["--paginate", "--slurp"])
    result = subprocess.run(command, capture_output=True, encoding="utf-8", timeout=120)  # nosec B603
    if result.returncode:
        raise RuntimeError(f"GitHub API {endpoint}: {result.stderr.strip()}")
    return json.loads(result.stdout)


def measure(run, repo):
    run_id, sha, attempt = run["id"], run["head_sha"], run["run_attempt"]
    base = f"repos/{repo}"
    try:
        jobs = github(f"{base}/actions/runs/{run_id}/attempts/{attempt}/jobs?per_page=100", paginate=True)
        jobs = [job for page in jobs for job in page["jobs"] if job["conclusion"] != "skipped"]
        started = min(timestamp(job["started_at"]) for job in jobs)
        completed = max(timestamp(job["completed_at"]) for job in jobs)
        created = timestamp(run["created_at"])
        if not created <= started <= completed:
            raise ValueError("job timestamps are out of order")
        row = {
            "id": run_id,
            "sha": sha,
            "attempt": attempt,
            "conclusion": run["conclusion"],
            "completed_at": completed,
            "queue_seconds": (started - created).total_seconds(),
            "execution_seconds": (completed - started).total_seconds(),
        }
        if run["conclusion"] == "success":
            pages = github(f"{base}/commits/{sha}/pulls?per_page=100", paginate=True)
            matching = [
                pr["number"]
                for page in pages
                for pr in page
                if pr["merged_at"] and pr["merge_commit_sha"] == sha and pr["base"]["ref"] == "main"
            ]
            if len(matching) > 1:
                raise ValueError("multiple PRs match the merge SHA")
            pr = matching[0] if matching else None
            if pr is None:
                commit = github(f"{base}/commits/{sha}")
            else:
                commit = github(f"{base}/pulls/{pr}/commits?per_page=1")[0]
            authored = timestamp(commit["commit"]["author"]["date"])
            if authored > created:
                raise ValueError("first commit timestamp is later than run creation")
            row.update(pr=pr, lead_seconds=(completed - authored).total_seconds())
        return row
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise ValueError(f"Run {run_id}: missing or invalid timing data ({error})") from error


def stats(values):
    return {
        "count": len(values),
        "mean_seconds": mean(values) if values else None,
        "median_seconds": median(values) if values else None,
    }


def calculate(runs, start, end):
    successful = sorted(
        (run for run in runs if run["conclusion"] == "success"),
        key=lambda run: run["completed_at"],
    )
    failed = [run for run in runs if run["conclusion"] == "failure"]
    recovery, missing = [], []
    for run in failed:
        last = run["completed_at"]
        next_green = next((green for green in successful if green["completed_at"] > last), None)
        if next_green is None:
            missing.append(run["id"])
        else:
            recovery.append((next_green["completed_at"] - last).total_seconds())

    lead = [run["lead_seconds"] for run in successful]
    total_lead = sum(lead)
    queue = sum(run["queue_seconds"] for run in successful)
    execution = sum(run["execution_seconds"] for run in successful)
    weeks = (end - start) / timedelta(weeks=1)
    return {
        "completed_runs": len(runs),
        "successful_runs": len(successful),
        "failed_runs": len(failed),
        "deployments_per_week": len(successful) / weeks,
        "change_failure_percent": len(failed) / len(runs) * 100 if runs else None,
        "lead_time": stats(lead),
        "direct_commits_in_lead_time": sum(run["pr"] is None for run in successful),
        "queue_seconds": queue,
        "execution_seconds": execution,
        "queue_percent_of_lead_time": queue / total_lead * 100 if total_lead else None,
        "execution_percent_of_lead_time": execution / total_lead * 100 if total_lead else None,
        "recovery_time": stats(recovery),
        "unrecovered_run_ids": missing,
    }


def collect(repo, workflow, start, end):
    # GitHub caps searches with filters at 1,000 results. Split busy ranges.
    query = urlencode(
        {
            "branch": "main",
            "event": "push",
            "created": f"{start.isoformat()}..{end.isoformat()}",
            "per_page": 100,
        }
    )
    endpoint = f"repos/{repo}/actions/workflows/{quote(workflow, safe='')}/runs?{query}"
    pages = github(endpoint, paginate=True)
    if pages[0]["total_count"] >= 1000:
        midpoint = (start + (end - start) / 2).replace(microsecond=0)
        if not start < midpoint < end:
            raise ValueError("GitHub capped a one-second interval at 1,000 runs")
        return collect(repo, workflow, start, midpoint) + collect(repo, workflow, midpoint, end)
    return [
        run
        for page in pages
        for run in page["workflow_runs"]
        if run["status"] == "completed" and start <= timestamp(run["created_at"]) < end
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="OWNER/REPOSITORY")
    parser.add_argument("--workflow", required=True, help="workflow file name or numeric ID")
    parser.add_argument("--from", dest="start", required=True, help="inclusive ISO timestamp")
    parser.add_argument("--to", dest="end", required=True, help="exclusive ISO timestamp")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        owner, separator, repo = args.repo.partition("/")
        if (
            not separator
            or not owner
            or not repo
            or any(not part.replace("-", "").replace("_", "").replace(".", "").isalnum() for part in (owner, repo))
        ):
            raise ValueError("--repo must be OWNER/REPOSITORY")
        start, end = timestamp(args.start), timestamp(args.end)
        if start >= end or start.microsecond or end.microsecond:
            raise ValueError("Use increasing --from and --to timestamps at second precision")
        runs = collect(args.repo, args.workflow, start, end)
        with ThreadPoolExecutor(max_workers=5) as pool:
            rows = list(pool.map(lambda run: measure(run, args.repo), runs))
        report = {
            "repository": args.repo,
            "workflow": args.workflow,
            "from": start.isoformat(),
            "to_exclusive": end.isoformat(),
            "Використання ШІ": "Codex додав автоматичний підрахунок. Результат звірено зі звітом Lab 10.",
            **calculate(rows, start, end),
        }
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, KeyError, IndexError, TypeError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        parser.exit(1, f"ci_metrics: {error}\n")


if __name__ == "__main__":
    main()
