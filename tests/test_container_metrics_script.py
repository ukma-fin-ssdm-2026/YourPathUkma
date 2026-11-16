# Використання ШІ: Codex додав тести зіставлення джерела й публікації. Перевірка: pytest.
from datetime import datetime, timedelta, timezone

from scripts import container_metrics as module


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
    })
    assert "50.00%" in table
    assert "180.00 / 180.00 с" in table
