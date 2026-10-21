# Test quality notes

Author: Test Lead. State on 2026-10-21: 216 tests, 86 % line and branch coverage, CI fails below 80 %.

## What was added

| File | Style | What it checks |
|---|---|---|
| `tests/test_admin_sync_unit.py` | mocks, no DB | `_check_change`, `_apply_change` and response builders of the moderation queue |
| `tests/test_deanery_unit.py` | mocks, no DB | `process_document` (parser and session patched), academic-year boundary, history import |
| `tests/test_admin_common_unit.py` | mocks, no DB | `client_ip`, `write_audit`, `require_admin`, audit log fields |
| `tests/test_admin_api.py` | real DB, `admin_client` | users, directions and audit-log endpoints: filters, 404, 409, 422, audit rows |

Shared fixtures live in `tests/conftest.py`: `fake_session` (`MagicMock(spec=Session)`), `make_item` (factory of moderation items) and `admin_client` (TestClient authenticated as the seed admin through `dependency_overrides`).

## When to mock and when to use the real database

- **Mock** helpers that receive a `Session` or call an external collaborator (parser, clock): the test then checks decisions and calls (`add`, `flush`, `rollback`, `commit`) and runs in milliseconds.
- **Real database** for endpoints: query building, filters and constraints (unique names, foreign keys) are the point of the test, and a mock would only repeat the implementation.
- Create mocks with `spec=Session`, so a typo in a method name fails the test instead of silently passing.

## Rules the new tests follow

1. AAA layout (Arrange, Act, Assert), one behaviour per test, names like `test_<unit>_<situation>`.
2. Parametrization instead of copy-paste for boundaries (credits limits, 1 September, invalid hosts, invalid query parameters).
3. Deterministic: dates are passed as arguments, no network, no sleeps, no dependence on test order.
4. Isolation of the shared seed data: tests that change it restore it in `finally` or create uniquely named records and delete them.
5. Regression tests for real bugs, for example `client_ip("testclient")` returns `None` (the `inet` column failed on PostgreSQL).

## Coverage: what is intentionally not covered

- `admin/sync.py` endpoints that start and review sync jobs (60 %): the SAZ parser is not connected yet, so there is no real behaviour to test.
- `main.py` lifespan, `db/migrate.py`, `db/seed.py`, `db/config.py`: start-up and tooling code, checked implicitly by every test run.
- Remaining branches of `user.py` and `preferences.py` (73-82 %).
- 100 % is not a goal: the gate is 80 % and the report shows where the real gaps are.

## Suggestions for the next steps

1. Cover the moderation endpoints (`approve`, `reject`, `bulk-review`) once the parser creates real jobs, using a factory for `SyncJob` and `ModerationItem` rows.
2. Add property-based tests (Hypothesis) for `plan_rules`, for example "the free-elective check never reports a violation for totals up to 25".
3. Run mutation testing on `src/services/plan_rules.py` (100 % covered pure logic). `mutmut` needs Linux, so run it in CI or Docker.
4. Move the repeated `session_factory()()` clean-up in `test_admin_api.py` into a fixture if more tests modify the shared database.
5. Keep the CI threshold slightly under the real number and raise it when coverage grows.
