from __future__ import annotations

import base64
import os

import requests
import streamlit as st

API_BASE = os.getenv("BACKEND_URL", "http://localhost:8000")


def render_pdf_viewer() -> None:
    doc_id = st.session_state.get("current_doc_id")
    if not doc_id:
        return

    selected_doc = next(
        (d for d in st.session_state.documents if d["doc_id"] == doc_id),
        None,
    )
    filename = selected_doc["filename"] if selected_doc else "document.pdf"

    st.markdown(
        f"<div style='font-size:0.82rem; color:#8892a4; margin-bottom:0.5rem'>"
        f"📄 <b style='color:#a0aec0'>{filename}</b>"
        f"</div>",
        unsafe_allow_html=True,
    )

    cache_key = f"_pdf_bytes_{doc_id}"
    if cache_key not in st.session_state:
        try:
            resp = requests.get(
                f"{API_BASE}/documents/{doc_id}/file",
                timeout=30,
            )
            resp.raise_for_status()
            st.session_state[cache_key] = resp.content
        except requests.ConnectionError:
            st.warning("Cannot load PDF. Is the backend running?")
            return
        except Exception as e:
            st.warning(f"Could not load PDF: {e}")
            return

    pdf_bytes = st.session_state[cache_key]
    b64 = base64.b64encode(pdf_bytes).decode("utf-8")

    st.markdown(
        f"""
        <iframe
            src="data:application/pdf;base64,{b64}"
            width="100%"
            height="700px"
            style="border: 1px solid #2a2f3e; border-radius: 8px;"
        ></iframe>
        """,
        unsafe_allow_html=True,
    )
