from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_query_requires_doc():
    r = client.post("/query", json={"doc_id": "missing", "question": "What is this?", "top_k": 3})
    assert r.status_code == 404


def test_query_validation_short_question():
    r = client.post("/query", json={"doc_id": "x", "question": "a"})
    assert r.status_code in (400, 422)

def test_query_response_schema_when_missing_doc():
    r = client.post("/query", json={"doc_id": "missing", "question": "hello world", "top_k": 5})
    assert r.status_code == 404
