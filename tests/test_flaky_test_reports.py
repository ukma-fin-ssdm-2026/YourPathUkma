# Використання ШІ: Codex додав перевірки класифікації JUnit-звітів.
# Перевірка: pytest для цього модуля.
from scripts.flaky_test_reports import compare


def test_compare_classifies_results_and_incomplete_rounds(tmp_path):
    for index in range(1, 6):
        if index == 5:
            continue
        cases = '<testcase classname="suite" name="green"/>'
        cases += '<testcase classname="suite" name="red"><failure/></testcase>'
        if index != 4:
            status = "<failure/>" if index == 2 else ""
            cases += f'<testcase classname="suite" name="flaky">{status}</testcase>'
        (tmp_path / f"backend-{index}.xml").write_text(f"<testsuite>{cases}</testsuite>", encoding="utf-8")
        (tmp_path / f"backend-{index}.exit").write_text("1", encoding="utf-8")

    result = compare(tmp_path, "backend", 5)

    assert result["flaky"] == {"suite::flaky": ["failed", "passed"]}
    assert result["stable_failures"] == ["suite::red"]
    assert set(result["incomplete"]) == {4, 5}
