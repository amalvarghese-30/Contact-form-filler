"""API endpoint smoke and validation tests using FastAPI TestClient."""

import sys
from pathlib import Path
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi_backend import app

client = TestClient(app)


def test_health_endpoint():
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["app"] == "Contact Form Filler"
    assert body["status"] in ("ok", "degraded")


def test_api_health_endpoint():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert "database" in res.json()


def test_settings_endpoint():
    res = client.get("/api/settings")
    assert res.status_code == 200
    body = res.json()
    assert "automation" in body
    assert "status" in body
    assert body["status"]["backend"] == "connected"


def test_create_website_rejects_ssrf_url():
    res = client.post("/api/websites", json={"url": "http://169.254.169.254/latest/meta-data/"})
    assert res.status_code == 400


def test_create_campaign_rejects_empty_name():
    res = client.post("/api/campaigns", json={"name": "", "websiteIds": []})
    assert res.status_code == 422
