from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_upload_pdf_success(tmp_path, monkeypatch):
    # Make storage go to a temp folder during tests
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))

    fake_pdf = b"%PDF-1.4\n%fake\n1 0 obj\n<<>>\nendobj\n%%EOF"
    files = {"file": ("sample.pdf", fake_pdf, "application/pdf")}

    r = client.post("/documents", files=files)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "doc_id" in data
    assert data["filename"] == "sample.pdf"
    assert data["stored_path"].endswith(".pdf")


def test_upload_reject_non_pdf(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))

    files = {"file": ("note.txt", b"hello", "text/plain")}
    r = client.post("/documents", files=files)
    assert r.status_code == 400