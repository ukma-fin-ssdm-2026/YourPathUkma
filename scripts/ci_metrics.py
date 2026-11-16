# Використання ШІ: Codex додав підрахунок і підтримку GH_TOKEN для GitHub Actions.
# Перевірка: pytest і відтворення історичної вибірки GitHub Actions.
# Використання ШІ: Codex врахував доставлені пізніше зміни й перекриття інтервалів CI.
# Перевірка: pytest, Ruff і локальне відтворення JSON-доказів з перевіркою предків Git.
# Codex додав обмежені повтори GET-запитів. Перевірка: ін’єкція збоїв і запуск workflow.
"""Reproduce the Lab 10 CI metrics from GitHub Actions."""

import argparse
import http.client
import json
import os
import re
import shutil
import subprocess  # nosec B404
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from functools import cache
from statistics import mean, median
from urllib.parse import quote, urlencode, urlsplit


def timestamp(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError(f"Expected a timestamp with a UTC offset: {value}")
    return parsed.astimezone(timezone.utc)


@cache
def github_token():
    if token := os.environ.get("GH_TOKEN"):
        return token
    executable = shutil.which("gh")
    if executable is None:
        raise RuntimeError("Install the GitHub CLI (gh)")
    result = subprocess.run(  # nosec B603
        [executable, "auth", "token", "--hostname", "github.com"],
        capture_output=True,
        encoding="utf-8",
        timeout=30,
    )
    if result.returncode or not result.stdout.strip():
        raise RuntimeError("Authenticate for github.com with gh auth login")
    return result.stdout.strip()


def github_page(endpoint, headers):
    for attempt in range(4):
        delay = 2**attempt
        connection = http.client.HTTPSConnection("api.github.com", timeout=30)
        try:
            connection.request("GET", "/" + endpoint, headers=headers)
            response = connection.getresponse()
            if response.status == 200:
                return json.loads(response.read()), response.getheader("Link", "")
            retry_after = response.getheader("Retry-After")
            failure = f"HTTP {response.status}"
            retryable = response.status == 429 or 500 <= response.status < 600
            if response.status == 403 and retry_after:
                retryable = True
            if retry_after and retry_after.isdecimal():
                delay = max(delay, int(retry_after))
            if not retryable:
                raise RuntimeError(f"GitHub API {endpoint}: {failure}")
        except (TimeoutError, ConnectionError, http.client.IncompleteRead) as error:
            failure = type(error).__name__
        finally:
            connection.close()
        if attempt == 3 or delay > 60:
            raise RuntimeError(f"GitHub API {endpoint}: {failure} after {attempt + 1} attempt(s)")
        time.sleep(delay)


def github(endpoint, *, paginate=False):
    headers = {
        "Authorization": f"Bearer {github_token()}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "YourPathUkma-Lab10",
    }
    pages = []
    while endpoint:
        data, links = github_page(endpoint, headers)
        if not paginate:
            return data
        pages.append(data)
        link = re.search(r'<([^>]+)>; rel="next"', links)
        if not link:
            break
        next_page = urlsplit(link.group(1))
        if next_page.scheme != "https" or next_page.netloc != "api.github.com":
            raise ValueError("Unexpected pagination host")
        endpoint = f"{next_page.path.lstrip('/')}?{next_page.query}"
    return pages


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
            "created_at": created,
            "started_at": started,
            "completed_at": completed,
            "queue_seconds": (started - created).total_seconds(),
            "execution_seconds": (completed - started).total_seconds(),
        }
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
        row.update(pr=pr, authored_at=authored)
        return row
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise ValueError(f"Run {run_id}: missing or invalid timing data ({error})") from error


def stats(values):
    return {
        "count": len(values),
        "mean_seconds": mean(values) if values else None,
        "median_seconds": median(values) if values else None,
    }


@cache
def contains_commit(repo, base, head):
    if base == head:
        return True
    comparison = github(f"repos/{repo}/compare/{base}...{head}?per_page=1")
    return comparison["status"] in {"ahead", "identical"}


def interval_seconds(intervals):
    """Measure the union of wall-clock intervals, without double-counting overlaps."""
    total, last = 0, None
    for start, end in sorted(intervals):
        if end > start:
            total += max(0, (end - max(start, last or start)).total_seconds())
            last = max(end, last or end)
    return total


def delivery_timing(attempts, delivery, authored):
    # Count this SHA's attempts and its delivering run; clip at delivery completion.
    # Execution takes precedence over queue time during overlapping runs.
    relevant = {run["id"]: run for run in [*attempts, delivery]}
    finish = delivery["completed_at"]
    queue, execution = [], []
    for run in relevant.values():
        queue.append((max(authored, run["created_at"]), min(finish, run["started_at"])))
        execution.append((max(authored, run["started_at"]), min(finish, run["completed_at"])))
    executing = interval_seconds(execution)
    return interval_seconds(queue + execution) - executing, executing


def calculate(runs, start, end, contains=None):
    contains = contains or (lambda base, head: base == head)
    successful = sorted(
        (run for run in runs if run["conclusion"] == "success"),
        key=lambda run: (run["completed_at"], run["id"]),
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

    by_sha = {}
    for run in sorted(runs, key=lambda run: (run["created_at"], run["id"])):
        by_sha.setdefault(run["sha"], []).append(run)
    changes, undelivered = [], []
    for sha, attempts in by_sha.items():
        source = attempts[0]
        delivery = next(
            (
                green
                for green in successful
                if green["completed_at"] >= source["created_at"] and contains(sha, green["sha"])
            ),
            None,
        )
        if delivery is None:
            undelivered.append(sha)
            continue
        queue, execution = delivery_timing(attempts, delivery, source["authored_at"])
        lead = (delivery["completed_at"] - source["authored_at"]).total_seconds()
        changes.append(
            {
                "sha": sha,
                "pr": source["pr"],
                "source_run_id": source["id"],
                "delivery_run_id": delivery["id"],
                "lead_seconds": lead,
                "queue_seconds": queue,
                "execution_seconds": execution,
                "other_seconds": lead - queue - execution,
            }
        )
    lead = [change["lead_seconds"] for change in changes]
    total_lead = sum(lead)
    queue = sum(change["queue_seconds"] for change in changes)
    execution = sum(change["execution_seconds"] for change in changes)
    weeks = (end - start) / timedelta(weeks=1)
    return {
        "completed_runs": len(runs),
        "successful_runs": len(successful),
        "failed_runs": len(failed),
        "deployments_per_week": len(successful) / weeks,
        "change_failure_percent": len(failed) / len(runs) * 100 if runs else None,
        "lead_time": stats(lead),
        "direct_commits_in_lead_time": sum(change["pr"] is None for change in changes),
        "queue_seconds": queue,
        "execution_seconds": execution,
        "other_seconds": total_lead - queue - execution,
        "queue_percent_of_lead_time": queue / total_lead * 100 if total_lead else None,
        "execution_percent_of_lead_time": execution / total_lead * 100 if total_lead else None,
        "recovery_time": stats(recovery),
        "unrecovered_run_ids": missing,
        "undelivered_change_shas": undelivered,
        "lead_time_changes": changes,
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
    parser.add_argument("--output", choices=("-",), default="-", help="emit JSON on stdout")
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
            **calculate(rows, start, end, lambda base, head: contains_commit(args.repo, base, head)),
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
    except (OSError, KeyError, IndexError, TypeError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        parser.exit(1, f"ci_metrics: {error}\n")


if __name__ == "__main__":
    main()
