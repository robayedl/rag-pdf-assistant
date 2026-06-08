"""Tests for the MCP server module (auth and tools)."""
from __future__ import annotations

import hashlib
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# mcp_server.auth
# ---------------------------------------------------------------------------

def test_hash_key_is_deterministic():
    from mcp_server.auth import hash_key

    assert hash_key("dm_abc") == hash_key("dm_abc")
    assert hash_key("dm_abc") == hashlib.sha256(b"dm_abc").hexdigest()


def test_hash_key_differs_per_key():
    from mcp_server.auth import hash_key

    assert hash_key("dm_abc") != hash_key("dm_xyz")


def _mock_conn(row=None):
    """Return a mock psycopg2 connection that yields the given row."""
    cur = MagicMock()
    cur.__enter__ = MagicMock(return_value=cur)
    cur.__exit__ = MagicMock(return_value=False)
    cur.fetchone.return_value = row

    conn = MagicMock()
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value = cur
    return conn, cur


def test_validate_api_key_returns_user_id_for_valid_key():
    from mcp_server.auth import hash_key, validate_api_key

    key = "dm_testkey123"
    conn, cur = _mock_conn(row=("user_abc",))

    with patch("mcp_server.auth.psycopg2.connect", return_value=conn):
        result = validate_api_key(key)

    assert result == "user_abc"
    # should have looked up by hash
    call_args = cur.execute.call_args_list[0][0]
    assert hash_key(key) in call_args[1]


def test_validate_api_key_returns_none_for_unknown_key():
    from mcp_server.auth import validate_api_key

    conn, _ = _mock_conn(row=None)

    with patch("mcp_server.auth.psycopg2.connect", return_value=conn):
        result = validate_api_key("dm_unknown")

    assert result is None


def test_validate_api_key_returns_none_for_empty_string():
    from mcp_server.auth import validate_api_key

    result = validate_api_key("")
    assert result is None


def test_validate_api_key_returns_none_on_db_error():
    from mcp_server.auth import validate_api_key

    with patch("mcp_server.auth.psycopg2.connect", side_effect=Exception("conn failed")):
        result = validate_api_key("dm_any")

    assert result is None


# ---------------------------------------------------------------------------
# mcp_server.server — tools (user injected via ContextVar)
# ---------------------------------------------------------------------------

def _set_user(user_id: str):
    from mcp_server.server import _user_id_var
    return _user_id_var.set(user_id)


def test_list_documents_returns_rows():
    from mcp_server.server import list_documents

    row = {"doc_id": "abc", "filename": "paper.pdf", "page_count": 5, "created_at": "2026-01-01"}
    conn, cur = _mock_conn()
    cur.fetchall.return_value = [row]

    token = _set_user("user_1")
    try:
        with patch("mcp_server.server.psycopg2.connect", return_value=conn):
            result = list_documents()
    finally:
        from mcp_server.server import _user_id_var
        _user_id_var.reset(token)

    assert len(result) == 1
    assert result[0]["filename"] == "paper.pdf"


def test_get_document_returns_metadata():
    from mcp_server.server import get_document

    row = {
        "doc_id": "abc",
        "filename": "paper.pdf",
        "page_count": 3,
        "status": "indexed",
        "created_at": "2026-01-01",
        "preview": "This is the beginning of the document content.",
    }
    conn, cur = _mock_conn(row=row)

    token = _set_user("user_1")
    try:
        with patch("mcp_server.server.psycopg2.connect", return_value=conn):
            result = get_document("abc")
    finally:
        from mcp_server.server import _user_id_var
        _user_id_var.reset(token)

    assert result["filename"] == "paper.pdf"
    assert "first_500_chars" in result
    assert "preview" not in result


def test_get_document_returns_error_for_missing_doc():
    from mcp_server.server import get_document

    conn, cur = _mock_conn(row=None)

    token = _set_user("user_1")
    try:
        with patch("mcp_server.server.psycopg2.connect", return_value=conn):
            result = get_document("nonexistent-id")
    finally:
        from mcp_server.server import _user_id_var
        _user_id_var.reset(token)

    assert "error" in result


def test_search_documents_returns_ranked_results():
    from langchain_core.documents import Document as LCDoc
    from mcp_server.server import search_documents

    fake_docs = [
        LCDoc(page_content="Neural networks are powerful.", metadata={"filename": "ml.pdf", "page": 1, "ref": "r1"}),
        LCDoc(page_content="Deep learning requires data.", metadata={"filename": "ml.pdf", "page": 2, "ref": "r2"}),
    ]

    conn, cur = _mock_conn()
    cur.fetchall.return_value = [("doc-uuid-1",)]

    token = _set_user("user_1")
    try:
        with (
            patch("mcp_server.server.psycopg2.connect", return_value=conn),
            patch("mcp_server.server.hybrid_search", return_value=fake_docs),
        ):
            result = search_documents("neural networks", top_k=2)
    finally:
        from mcp_server.server import _user_id_var
        _user_id_var.reset(token)

    assert len(result) == 2
    assert result[0]["content"] == "Neural networks are powerful."
    assert result[0]["score"] > result[1]["score"]


def test_search_documents_clamps_top_k():
    from mcp_server.server import search_documents

    conn, cur = _mock_conn()
    cur.fetchall.return_value = []

    token = _set_user("user_1")
    try:
        with patch("mcp_server.server.psycopg2.connect", return_value=conn):
            result = search_documents("query", top_k=999)
    finally:
        from mcp_server.server import _user_id_var
        _user_id_var.reset(token)

    assert result == []


def test_require_user_raises_without_context_or_env():
    from mcp_server.server import _require_user

    with patch("mcp_server.server.key_from_env", return_value=None):
        with pytest.raises(RuntimeError, match="DOCUMIND_API_KEY"):
            _require_user()
