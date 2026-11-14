# Використання ШІ: Codex додав перевірки меж вибірки, прямих комітів і відновлення.
# Перевірка: окремий запуск pytest для цього модуля.
from datetime import timedelta

from scripts.ci_metrics import calculate, collect, timestamp


def test_calculate_keeps_unrecovered_failures_and_uses_full_lead_time():
    start = timestamp("2026-10-23T00:00:00Z")
    runs = [
        {
            "id": 1,
            "conclusion": "success",
            "completed_at": start + timedelta(seconds=60),
            "lead_seconds": 120,
            "queue_seconds": 12,
            "execution_seconds": 24,
            "pr": None,
        },
        {
            "id": 2,
            "conclusion": "failure",
            "completed_at": start + timedelta(seconds=30),
        },
        {
            "id": 3,
            "conclusion": "failure",
            "completed_at": start + timedelta(seconds=90),
        },
    ]

    report = calculate(runs, start, start + timedelta(days=7))

    assert report["deployments_per_week"] == 1
    assert report["change_failure_percent"] == 2 / 3 * 100
    assert report["lead_time"]["mean_seconds"] == 120
    assert report["queue_percent_of_lead_time"] == 10
    assert report["execution_percent_of_lead_time"] == 20
    assert report["recovery_time"]["median_seconds"] == 30
    assert report["unrecovered_run_ids"] == [3]


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
