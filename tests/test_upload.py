def test_upload_pdf_success(tmp_path, monkeypatch, authed_client):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    fake_pdf = b"%PDF-1.4\n%fake\n1 0 obj\n<<>>\nendobj\n%%EOF"
    r = authed_client.post("/documents", files={"file": ("sample.pdf", fake_pdf, "application/pdf")})
    assert r.status_code == 200, r.text
    data = r.json()
    assert "doc_id" in data
    assert data["filename"] == "sample.pdf"


def test_upload_reject_non_pdf(tmp_path, monkeypatch, authed_client):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    r = authed_client.post("/documents", files={"file": ("note.txt", b"hello", "text/plain")})
    assert r.status_code == 400


def test_upload_requires_auth():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as client:
        r = client.post("/documents", files={"file": ("sample.pdf", b"%PDF", "application/pdf")})
    assert r.status_code in (401, 403)
