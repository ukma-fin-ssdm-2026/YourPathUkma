"""
Тести надійності: граничні випадки вводу (Лаб 9, знахідки №7, №8, №11).

Завантаження документа деканату (порожній файл, рівно ліміт, ліміт + 1 байт, регістр розширення, межі
`academic_year`), кількість сторінок каталогу САЗ, межі терміну дії JWT.

Використання ШІ: файл створено за допомогою Claude (Claude Code). Перевірка: запуск `pytest tests/reliability`.
"""

import time
from types import SimpleNamespace

import jwt
import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.routes.deanery import MAX_UPLOAD_BYTES
from src.api.tokens import JWT_AUDIENCE, JWT_ISSUER, decode_access_token, get_auth_settings
from src.parser.sync import MAX_PAGES, SyncFailure, _scan

client = TestClient(app)
AUTH = {"Authorization": "Bearer test"}


def _upload(content: bytes, filename="plan.pdf", content_type="application/pdf", year=2026):
    return client.post(
        "/api/v1/deanery-documents",
        files={"file": (filename, content, content_type)},
        data={"academic_year": year},
        headers=AUTH,
    )


def test_empty_file_is_rejected():
    response = _upload(b"")
    assert response.status_code == 422
    assert response.json()["code"] == "EMPTY_FILE"


def test_file_of_exactly_max_size_is_accepted():
    assert _upload(b"0" * MAX_UPLOAD_BYTES).status_code == 202


def test_file_one_byte_over_limit_is_rejected():
    response = _upload(b"0" * (MAX_UPLOAD_BYTES + 1))
    assert response.status_code == 413
    assert response.json()["code"] == "FILE_TOO_LARGE"


@pytest.mark.parametrize("filename", ["SCAN.PDF", "Plan.Docx"])
def test_uppercase_extension_is_recognised_when_mime_is_generic(filename):
    assert _upload(b"data", filename=filename, content_type="application/octet-stream").status_code == 202


def test_unknown_extension_is_rejected_with_415():
    response = _upload(b"data", filename="virus.exe", content_type="application/octet-stream")
    assert response.status_code == 415


@pytest.mark.parametrize("year,expected", [(2023, 422), (2024, 202), (2030, 202), (2031, 422)])
def test_academic_year_boundaries(year, expected):
    assert _upload(b"%PDF-1.4", year=year).status_code == expected


class _FakeFetcher:
    def __init__(self):
        self.pages = []

    def fetch(self, page):
        self.pages.append(page)
        return f"<html>{page}</html>"


class _FakeParser:
    def __init__(self, last_page):
        self._last_page = last_page

    def parse(self, _html):
        return SimpleNamespace(total=1, last_page=self._last_page)


def test_scan_visits_every_page_up_to_the_limit():
    fetcher = _FakeFetcher()
    pages, _total, _html = _scan(fetcher, _FakeParser(MAX_PAGES))
    assert len(pages) == MAX_PAGES
    assert fetcher.pages[-1] == MAX_PAGES


def test_scan_refuses_to_walk_more_pages_than_the_limit():
    fetcher = _FakeFetcher()
    with pytest.raises(SyncFailure):
        _scan(fetcher, _FakeParser(MAX_PAGES + 1))
    assert fetcher.pages == [1]  # далі першої сторінки не йдемо


def _token(**overrides):
    now = int(time.time())
    claims = {"sub": "42", "iat": now, "exp": now + 60, "iss": JWT_ISSUER, "aud": JWT_AUDIENCE}
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, get_auth_settings().jwt_secret, algorithm="HS256")


def test_token_valid_for_one_more_minute_is_accepted():
    assert decode_access_token(_token()) == 42


def test_expired_token_is_rejected():
    assert decode_access_token(_token(exp=int(time.time()) - 1)) is None


def test_token_without_exp_is_rejected():
    assert decode_access_token(_token(exp=None)) is None


def test_token_with_non_numeric_subject_is_rejected():
    assert decode_access_token(_token(sub="abc")) is None
