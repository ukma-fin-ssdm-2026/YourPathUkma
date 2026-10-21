"""Тести завантаження та перегляду документів деканату."""

from fastapi.testclient import TestClient

from src.api.main import app

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

def test_get_unknown_document_returns_404():
    response = client.get("/api/v1/deanery-documents/9999", headers=AUTH)
    assert response.status_code == 404
