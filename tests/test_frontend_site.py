"""
Роздача зібраного фронтенду з API-процесу: файли, запасний index.html для маршрутів SPA, незайманий API.

Використання ШІ: файл створено за допомогою Claude (Claude Code). Перевірка: pytest.
"""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.frontend_site import frontend_dist, mount_frontend

INDEX = "<!doctype html><title>YourPath</title><div id=root></div>"


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text(INDEX, encoding="utf-8")
    (tmp_path / "assets" / "app.js").write_text("console.log('app')", encoding="utf-8")
    (tmp_path / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    return tmp_path


@pytest.fixture
def client(dist: Path) -> TestClient:
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/v1/ping")
    def ping():
        return {"pong": True}

    assert mount_frontend(app, dist) is True
    return TestClient(app)


def test_root_serves_index(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "YourPath" in response.text


def test_static_asset_is_served_as_is(client):
    response = client.get("/assets/app.js")
    assert response.status_code == 200
    assert response.text == "console.log('app')"


def test_spa_route_falls_back_to_index(client):
    response = client.get("/path/create")
    assert response.status_code == 200
    assert "YourPath" in response.text


def test_api_routes_keep_priority(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/api/v1/ping").json() == {"pong": True}


def test_unknown_api_route_is_real_404_not_html(client):
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert "YourPath" not in response.text


def test_missing_build_asset_is_real_404_not_html(client):
    response = client.get("/assets/old-hash.js")
    assert response.status_code == 404
    assert "YourPath" not in response.text


def test_path_traversal_does_not_leave_the_dist_folder(client, dist):
    (dist.parent / "secret.txt").write_text("top secret", encoding="utf-8")
    response = client.get("/..%2fsecret.txt")
    assert "top secret" not in response.text


def test_not_mounted_without_a_build(tmp_path, monkeypatch):
    monkeypatch.setenv("FRONTEND_DIST", str(tmp_path / "missing"))
    app = FastAPI()
    assert mount_frontend(app) is False
    assert TestClient(app).get("/").status_code == 404


def test_frontend_dist_requires_index_html(tmp_path, monkeypatch):
    monkeypatch.setenv("FRONTEND_DIST", str(tmp_path))
    assert frontend_dist() is None
    (tmp_path / "index.html").write_text(INDEX, encoding="utf-8")
    assert frontend_dist() == tmp_path
