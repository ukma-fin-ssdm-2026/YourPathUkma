# Використання ШІ: Codex додав тести зіставлення джерела й публікації. Перевірка: pytest.
# Використання ШІ: Codex додав регресії спільної вибірки та виключених CI; перевірка: pytest і Ruff.
import json
import sys
from datetime import datetime, timedelta, timezone

import pytest

from scripts import container_metrics as module


def test_markdown_does_not_accept_an_arbitrary_destination(monkeypatch, tmp_path):
    destination = tmp_path / "outside-report.md"
    monkeypatch.setattr(sys, "argv", [
        "container_metrics", "--repo", "owner/repo",
        "--from", "2026-11-16T00:00:00Z", "--to", "2026-11-17T00:00:00Z",
        "--markdown", str(destination),
    ])
    with pytest.raises(SystemExit) as error:
        module.main()
    assert error.value.code == 2
    assert not destination.exists()


def test_publication_joins_source_id_instead_of_workflow_head_sha():
    now = datetime(2026, 11, 16, tzinfo=timezone.utc)
    source = {"id": 1, "sha": "a" * 40, "conclusion": "success", "completed_at": now}
    publication = {
        "id": 2, "head_sha": "b" * 40, "display_title": f"Publish {'a' * 40} CI 1",
        "status": "completed", "conclusion": "success", "run_attempt": 1,
        "updated_at": (now + timedelta(minutes=2)).isoformat(), "html_url": "https://example.com/run/2",
    }
    rows, pending = module.publication_rows([source], [publication], now + timedelta(days=1))
    assert not pending
    assert rows[0]["sha"] == source["sha"]
    assert rows[0]["completed_at"] == now + timedelta(minutes=2)
    assert rows[0]["publication_run_id"] == 2


def test_missing_or_out_of_window_publication_is_not_a_success():
    now = datetime(2026, 11, 16, tzinfo=timezone.utc)
    source = {"id": 1, "sha": "a" * 40, "conclusion": "success", "completed_at": now}
    failure = {**source, "id": 3, "conclusion": "failure"}
    rows, pending = module.publication_rows([source, failure], [], now + timedelta(days=1))
    assert pending == [1]
    assert rows == [failure]


def test_failed_publication_changes_failure_rate_and_recovery():
    now = datetime(2026, 11, 16, tzinfo=timezone.utc)
    sources, publications = [], []
    for index, conclusion in [(1, "failure"), (2, "success")]:
        sources.append({
            "id": index, "sha": str(index) * 40, "conclusion": "success", "pr": index,
            "authored_at": now, "created_at": now + timedelta(minutes=index),
            "started_at": now + timedelta(minutes=index, seconds=10),
            "completed_at": now + timedelta(minutes=index, seconds=20),
        })
        publications.append({
            "id": index + 10, "display_title": f"Publish {str(index) * 40} CI {index}",
            "status": "completed", "conclusion": conclusion, "run_attempt": 1,
            "updated_at": (now + timedelta(minutes=index + 1)).isoformat(), "html_url": "https://example.com",
        })
    rows, pending = module.publication_rows(sources, publications, now + timedelta(days=1))
    result = module.calculate(rows, now, now + timedelta(weeks=1), lambda base, head: base <= head)
    assert not pending
    assert result["change_failure_percent"] == 50
    assert result["deployments_per_week"] == 1
    assert result["recovery_time"]["mean_seconds"] == 60
    assert result["lead_time"]["count"] == 2
    assert result["lead_time"]["mean_seconds"] == 180
    table = module.comparison_table({
        "from": now.isoformat(), "to_exclusive": (now + timedelta(weeks=1)).isoformat(),
        "ci": result, "ghcr": result, "pending_publication_ci_ids": [], "complete_comparison": True,
        "excluded_ci_runs": [],
    })
    assert "50.00%" in table
    assert "180.00 / 180.00 с" in table


@pytest.mark.parametrize("conclusion", ["cancelled", "timed_out", "neutral", "skipped", "action_required", "stale"])
@pytest.mark.parametrize("only_excluded", [False, True])
def test_comparison_filters_both_cohorts_before_loading_job_timings(
    monkeypatch, capsys, conclusion, only_excluded,
):
    now = datetime(2026, 11, 16, tzinfo=timezone.utc)
    sources = [
        {
            "id": index, "sha": str(index) * 40, "conclusion": status, "pr": index,
            "authored_at": now, "created_at": now + timedelta(minutes=index),
            "started_at": now + timedelta(minutes=index, seconds=10),
            "completed_at": now + timedelta(minutes=index, seconds=20),
        }
        for index, status in [(1, "failure"), (2, "success")]
    ]
    excluded = {"id": 9, "conclusion": conclusion}  # No jobs or timestamps.
    monkeypatch.setattr(module, "collect", lambda *args: [excluded] if only_excluded else [*sources, excluded])
    measured = []

    def measure(run, repo):
        assert run["id"] != 9, "Excluded CI must not require job timing data"
        measured.append(run["id"])
        return run

    monkeypatch.setattr(module, "measure", measure)
    monkeypatch.setattr(module, "contains_commit", lambda repo, base, head: base <= head)
    publications = [{
        "id": 3, "display_title": f"Publish {'2' * 40} CI 2", "status": "completed",
        "conclusion": "success", "run_attempt": 1, "updated_at": "2026-11-16T00:03:00Z",
        "html_url": "https://example.com/run/3",
    }]
    monkeypatch.setattr(module, "github", lambda *args, **kwargs: [{"workflow_runs": publications}])
    monkeypatch.setattr(sys, "argv", [
        "container_metrics", "--repo", "owner/repo",
        "--from", "2026-11-16T00:00:00Z", "--to", "2026-11-17T00:00:00Z",
    ])
    module.main()
    report = json.loads(capsys.readouterr().out)
    assert report["excluded_ci_runs"] == [excluded]
    assert report["pending_publication_ci_ids"] == []
    assert report["complete_comparison"] is (not only_excluded)
    assert sorted(measured) == ([] if only_excluded else [1, 2])
    assert report["ci"]["completed_runs"] == report["ghcr"]["completed_runs"] == (0 if only_excluded else 2)
    assert report["ci"]["change_failure_percent"] == report["ghcr"]["change_failure_percent"] == (
        None if only_excluded else 50
    )
    table = module.comparison_table(report)
    assert "Виключені з обох вибірок CI" in table
    assert conclusion in table


def test_publication_join_rejects_unfiltered_ci():
    with pytest.raises(ValueError, match="Filter CI conclusions"):
        module.publication_rows(
            [{"id": 9, "conclusion": "cancelled"}], [], datetime(2026, 11, 17, tzinfo=timezone.utc),
        )
