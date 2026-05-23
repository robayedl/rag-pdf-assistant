from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app

_404 = HTTPException(status_code=404, detail="Document not found.")


def test_query_requires_auth():
    with TestClient(app) as client:
        r = client.post("/query", json={"doc_id": "some-id", "question": "What is this?", "top_k": 3})
    assert r.status_code in (401, 403)


def test_query_returns_404_for_missing_doc(authed_client):
    with patch("app.main._get_doc_or_404", new=AsyncMock(side_effect=_404)):
        r = authed_client.post("/query", json={"doc_id": "missing-doc", "question": "What is this?", "top_k": 3})
    assert r.status_code == 404


def test_query_validation_short_question(authed_client):
    r = authed_client.post("/query", json={"doc_id": "x", "question": "a"})
    assert r.status_code in (400, 422)


def test_query_response_schema_on_missing_doc(authed_client):
    with patch("app.main._get_doc_or_404", new=AsyncMock(side_effect=_404)):
        r = authed_client.post("/query", json={"doc_id": "missing-doc", "question": "hello world", "top_k": 5})
    assert r.status_code == 404
