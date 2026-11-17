"""Тести завантаження та перегляду документів деканату.

Використання ШІ: Codex додав регресії для назв файлів. Перевірка: pytest на PostgreSQL.
"""

from urllib.parse import unquote

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.db.models.deanery import DeaneryPlanDocument
from src.db.session import session_factory

client = TestClient(app)
AUTH = {"Authorization": "Bearer test"}


def test_upload_deanery_document():
    file_content = b"%PDF-1.4 fake content"
    files = {"file": ("test.pdf", file_content, "application/pdf")}
    data = {"academic_year": 2026}

    response = client.post("/api/v1/deanery-documents", files=files, data=data, headers=AUTH)
    assert response.status_code == 202
    res_data = response.json()
    assert res_data["original_filename"] == "test.pdf"
    assert res_data["parse_status"] == "pending"


def test_list_deanery_documents():
    response = client.get("/api/v1/deanery-documents", headers=AUTH)
    assert response.status_code == 200
    assert "deanery_documents" in response.json()


def test_download_document_with_ukrainian_filename():
    filename = "План 2026.pdf"
    content = b"%PDF-1.4 fake content"
    upload = client.post(
        "/api/v1/deanery-documents",
        files={"file": (filename, content, "application/pdf")},
        data={"academic_year": 2026},
        headers=AUTH,
    )
    assert upload.status_code == 202
    assert upload.json()["original_filename"] == filename
    response = client.get(f"/api/v1/deanery-documents/{upload.json()['id']}/file", headers=AUTH)
    assert response.status_code == 200
    assert response.content == content
    fallback, encoded = response.headers["content-disposition"].split("; filename*=UTF-8''")
    assert fallback == 'attachment; filename="document.pdf"'
    assert unquote(encoded) == filename


def test_download_sanitizes_legacy_filename():
    upload = client.post(
        "/api/v1/deanery-documents",
        files={"file": ("test.pdf", b"%PDF-1.4 fake content", "application/pdf")},
        data={"academic_year": 2026},
        headers=AUTH,
    )
    assert upload.status_code == 202
    document_id = upload.json()["id"]
    with session_factory()() as db:
        doc = db.get(DeaneryPlanDocument, document_id)
        doc.original_filename = 'C:\\fakepath\\test"\r\n.pdf'
        db.commit()

    response = client.get(f"/api/v1/deanery-documents/{document_id}/file", headers=AUTH)
    assert response.status_code == 200
    assert response.headers["content-disposition"] == """attachment; filename="test.pdf"; filename*=UTF-8''test.pdf"""


@pytest.mark.parametrize("length, expected_status", [(255, 202), (256, 422)])
def test_upload_deanery_filename_length(length, expected_status):
    filename = "я" * (length - 4) + ".pdf"
    response = client.post(
        "/api/v1/deanery-documents",
        files={"file": (filename, b"%PDF-1.4 fake content", "application/pdf")},
        data={"academic_year": 2026},
        headers=AUTH,
    )
    assert response.status_code == expected_status
    if expected_status == 422:
        assert response.json()["code"] == "FILENAME_TOO_LONG"
    else:
        assert response.json()["original_filename"] == filename


def test_get_unknown_document_returns_404():
    response = client.get("/api/v1/deanery-documents/9999", headers=AUTH)
    assert response.status_code == 404
