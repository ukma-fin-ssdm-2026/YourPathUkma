# Coverage report

HTML coverage report for `src/` (line and branch coverage). Open `index.html` in a browser.

Generated on 2026-10-21 with:

```bash
python -m pytest -q --cov=src --cov-branch --cov-report=html:docs/testing/coverage
rm docs/testing/coverage/.gitignore   # coverage.py adds it and it would hide the report from git
```

Result: 216 tests passed, total coverage 86 % (CI fails below 80 %, see `.github/workflows/ci.yaml`).
