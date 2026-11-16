# Використання ШІ: Codex додав перевірки меж вибірки, прямих комітів і відновлення.
# Перевірка: окремий запуск pytest для цього модуля.
# Використання ШІ: Codex додав регресії доставки після збоїв, повторних спроб і перекриття CI.
# Перевірка: pytest і Ruff.
# Codex додав тести відновлення після мережевого збою.
from datetime import timedelta
from http.client import RemoteDisconnected
from unittest.mock import MagicMock

import pytest

from scripts import ci_metrics
from scripts.ci_metrics import calculate, collect, timestamp


def metric_run(run_id, sha, conclusion, created, started, completed, authored=0, pr=1):
    origin = timestamp("2026-10-23T00:00:00Z")
    return {
        "id": run_id,
        "sha": sha,
        "conclusion": conclusion,
        "pr": pr,
        "created_at": origin + timedelta(seconds=created),
        "started_at": origin + timedelta(seconds=started),
        "completed_at": origin + timedelta(seconds=completed),
        "authored_at": origin + timedelta(seconds=authored),
    }


def report_for(runs, contains=None):
    start = timestamp("2026-10-23T00:00:00Z")
    return calculate(runs, start, start + timedelta(days=7), contains)


def test_calculate_keeps_unrecovered_failures_and_uses_full_lead_time():
    runs = [
        metric_run(1, "green", "success", 24, 36, 60, authored=-60, pr=None),
        metric_run(2, "red", "failure", 1, 2, 30),
        metric_run(3, "unrecovered", "failure", 61, 62, 90),
    ]
    report = report_for(runs)
    assert report["deployments_per_week"] == 1
    assert report["change_failure_percent"] == 2 / 3 * 100
    assert report["lead_time"]["mean_seconds"] == 120
    assert report["queue_percent_of_lead_time"] == 10
    assert report["execution_percent_of_lead_time"] == 20
    assert report["recovery_time"]["median_seconds"] == 30
    assert report["unrecovered_run_ids"] == [3]
    assert report["undelivered_change_shas"] == ["red", "unrecovered"]


def test_failed_changes_use_first_green_containing_them_and_clip_overlaps():
    runs = [
        metric_run(1, "failed", "failure", 10, 12, 40),
        metric_run(2, "unrelated", "success", 20, 22, 25, authored=15),
        metric_run(3, "descendant", "success", 30, 35, 50, authored=29),
    ]
    report = report_for(runs, lambda base, head: base == head or (base, head) == ("failed", "descendant"))
    change = report["lead_time_changes"][0]
    assert change["delivery_run_id"] == 3  # The earlier green does not contain the change.
    assert change["lead_seconds"] == 50
    assert change["queue_seconds"] == 2  # Delivering run's queue overlaps failed execution.
    assert change["execution_seconds"] == 38  # Union [12, 40] and [35, 50].
    assert change["other_seconds"] == 10
    assert report["lead_time"]["count"] == 3
    assert report["undelivered_change_shas"] == []


def test_first_green_may_finish_before_the_changes_own_green_run():
    runs = [
        metric_run(1, "parent", "success", 10, 12, 60),
        metric_run(2, "child", "success", 20, 22, 40),
    ]
    report = report_for(runs, lambda base, head: base == head or (base, head) == ("parent", "child"))
    change = report["lead_time_changes"][0]
    assert change["delivery_run_id"] == 2
    assert change["lead_seconds"] == 40
    assert change["execution_seconds"] == 28  # Own run is clipped at delivery.


def test_retry_of_same_sha_is_one_change_and_includes_both_attempts():
    runs = [
        metric_run(1, "same", "failure", 10, 12, 20),
        metric_run(2, "same", "success", 10, 30, 40),
    ]
    report = report_for(runs)
    assert report["lead_time"]["count"] == 1
    assert report["lead_time"]["mean_seconds"] == 40
    assert report["queue_seconds"] == 12  # [10, 30] excluding execution [12, 20].
    assert report["execution_seconds"] == 18
    assert report["other_seconds"] == 10


def test_empty_sample_has_no_lead_time_or_shares():
    report = report_for([])
    assert report["lead_time"]["mean_seconds"] is None
    assert report["queue_percent_of_lead_time"] is None
    assert report["lead_time_changes"] == []


@pytest.mark.parametrize(
    "status,expected", [("ahead", True), ("identical", True), ("behind", False), ("diverged", False)]
)
def test_contains_commit_checks_comparison_direction(monkeypatch, status, expected):
    ci_metrics.contains_commit.cache_clear()
    request = MagicMock(return_value={"status": status})
    monkeypatch.setattr(ci_metrics, "github", request)
    assert ci_metrics.contains_commit("org/repo", "parent", "child") is expected
    request.assert_called_once_with("repos/org/repo/compare/parent...child?per_page=1")
    ci_metrics.contains_commit.cache_clear()


def test_measure_loads_first_commit_even_for_failed_ci(monkeypatch):
    run = {"id": 1, "head_sha": "red", "run_attempt": 1, "conclusion": "failure", "created_at": "2026-10-23T00:00:10Z"}

    def github(endpoint, *, paginate=False):
        if "/jobs?" in endpoint:
            return [
                {
                    "jobs": [
                        {
                            "conclusion": "failure",
                            "started_at": "2026-10-23T00:00:12Z",
                            "completed_at": "2026-10-23T00:00:20Z",
                        }
                    ]
                }
            ]
        if "/pulls?" in endpoint:
            return [
                [
                    {
                        "number": 210,
                        "merged_at": "2026-10-23T00:00:09Z",
                        "merge_commit_sha": "red",
                        "base": {"ref": "main"},
                    }
                ]
            ]
        assert endpoint == "repos/org/repo/pulls/210/commits?per_page=1"
        return [{"commit": {"author": {"date": "2026-10-23T00:00:00Z"}}}]

    monkeypatch.setattr(ci_metrics, "github", github)
    measured = ci_metrics.measure(run, "org/repo")
    assert measured["pr"] == 210
    assert measured["authored_at"] == timestamp("2026-10-23T00:00:00Z")


def test_collect_filters_completed_runs_locally_and_excludes_window_end(monkeypatch):
    start = timestamp("2026-10-23T00:00:00Z")
    end = start + timedelta(days=7)
    runs = [
        {"id": 1, "status": "completed", "created_at": start.isoformat()},
        {"id": 2, "status": "queued", "created_at": start.isoformat()},
        {"id": 3, "status": "completed", "created_at": end.isoformat()},
    ]

    def github(endpoint, *, paginate):
        assert paginate
        assert "status=" not in endpoint
        return [{"total_count": 3, "workflow_runs": runs[:2]}, {"workflow_runs": runs[2:]}]

    monkeypatch.setattr("scripts.ci_metrics.github", github)
    assert collect("org/repo", "ci.yaml", start, end) == runs[:1]


@pytest.mark.parametrize("first_status", [None, 429, 503, 404])
def test_github_retries_only_temporary_failures(monkeypatch, first_status):
    first, second = MagicMock(), MagicMock()
    if first_status is None:
        first.getresponse.side_effect = RemoteDisconnected()
    else:
        first.getresponse.return_value.status = first_status
        first.getresponse.return_value.getheader.return_value = None
    second.getresponse.return_value.status = 200
    second.getresponse.return_value.read.return_value = b'{"ok": true}'
    connect = MagicMock(side_effect=[first, second])
    monkeypatch.setattr(ci_metrics.http.client, "HTTPSConnection", connect)
    monkeypatch.setattr(ci_metrics, "github_token", lambda: "test")
    pauses = MagicMock()
    monkeypatch.setattr("time.sleep", pauses)

    if first_status == 404:
        with pytest.raises(RuntimeError, match="HTTP 404"):
            ci_metrics.github("repos/org/repo")
        assert connect.call_count == 1
        pauses.assert_not_called()
    else:
        assert ci_metrics.github("repos/org/repo") == {"ok": True}
        assert connect.call_count == 2
        pauses.assert_called_once_with(1)
        second.close.assert_called_once()
    first.close.assert_called_once()


def test_historical_evidence_reproduces_all_delivered_changes():
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "docs/ci-cd"
    evidence = json.loads((root / "evidence/lab10-main-ci.json").read_text())
    saved = json.loads((root / "lab10-automated-metrics.json").read_text())
    parents = {run["sha"]: run["parents"] for run in evidence["runs"]}

    def contains(base, head):
        pending, seen = [head], set()
        while pending:
            sha = pending.pop()
            if sha == base:
                return True
            if sha not in seen:
                seen.add(sha)
                pending.extend(parents.get(sha, []))
        return False

    rows = [
        {
            "id": run["id"],
            "sha": run["sha"],
            "conclusion": run["conclusion"],
            "pr": run["first_commit"]["pr"],
            "created_at": timestamp(run["created_at"]),
            "started_at": min(timestamp(job["started_at"]) for job in run["jobs"]),
            "completed_at": timestamp(run["completed_at"]),
            "authored_at": timestamp(run["first_commit"]["authored_at"]),
        }
        for run in evidence["runs"]
    ]
    report = calculate(rows, timestamp(evidence["from"]), timestamp(evidence["to_exclusive"]), contains)
    assert report["lead_time"]["count"] == 90
    assert report["lead_time"]["mean_seconds"] == pytest.approx(4505342 / 90)
    assert report["lead_time"]["median_seconds"] == 30434.5
    assert report["queue_seconds"] == 117740
    assert report["execution_seconds"] == 27248
    assert report["other_seconds"] == 4360354
    assert report["unrecovered_run_ids"] == report["undelivered_change_shas"] == []
    changed = {
        change["pr"] for change in report["lead_time_changes"] if change["source_run_id"] != change["delivery_run_id"]
    }
    assert changed == {154, 210, 211, 250}
    for change in report["lead_time_changes"]:
        assert change["lead_seconds"] == sum(
            change[key] for key in ("queue_seconds", "execution_seconds", "other_seconds")
        )
        assert change["other_seconds"] >= 0
    for key, value in report.items():
        assert saved[key] == value, key
