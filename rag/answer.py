from __future__ import annotations

import re
from typing import List

from rag.retrieve import RetrievedChunk
from rag.text_clean import normalize_keep_lines, normalize_one_line


_SKILLS_HEADERS = [
    r"TECHNICAL\s+SKILLS",
    r"SKILLS",
    r"TECHNICAL\s+SUMMARY",
]

# Spaced header variants like "T E C H N I C A L  S K I L L S"
_SPACED_TECH_SKILLS = r"T\s*E\s*C\s*H\s*N\s*I\s*C\s*A\s*L\s+S\s*K\s*I\s*L\s*L\s*S"
_SPACED_SKILLS = r"S\s*K\s*I\s*L\s*L\s*S"


def _header_regex() -> str:
    parts = _SKILLS_HEADERS + [_SPACED_TECH_SKILLS, _SPACED_SKILLS]
    return r"(" + "|".join(parts) + r")"


def _stop_regex() -> str:
    # Stop at next major resume section (normal or spaced)
    return r"(" \
           r"E\s*D\s*U\s*C\s*A\s*T\s*I\s*O\s*N|EDUCATION|" \
           r"E\s*X\s*P\s*E\s*R\s*I\s*E\s*N\s*C\s*E|EXPERIENCE|" \
           r"P\s*R\s*O\s*J\s*E\s*C\s*T\s*S?|PROJECTS?|" \
           r"R\s*E\s*S\s*E\s*A\s*R\s*C\s*H|RESEARCH|" \
           r"C\s*E\s*R\s*T\s*I\s*F\s*I\s*C\s*A\s*T\s*I\s*O\s*N\s*S?|CERTIFICATIONS?|" \
           r"A\s*W\s*A\s*R\s*D\s*S?|AWARDS?" \
           r")"


def _find_skills_section(text: str) -> str | None:
    t = normalize_keep_lines(text)

    header = re.search(_header_regex(), t, flags=re.IGNORECASE)
    if not header:
        return None

    tail = t[header.end():].strip()

    stop = re.search(_stop_regex(), tail, flags=re.IGNORECASE)
    if stop:
        tail = tail[: stop.start()].strip()

    if len(tail) < 40:
        return None

    return tail


def _join_wrapped_lines(block: str) -> str:
    """
    Many PDFs break phrases across lines:
      "Machine\nLearning\n&\nComputer Vision"
    This attempts to rejoin lines into more natural sentences, while preserving
    real section/category boundaries.
    """
    lines = [ln.strip() for ln in normalize_keep_lines(block).split("\n") if ln.strip()]
    out: List[str] = []

    def is_probably_category(line: str) -> bool:
        # "Frameworks & Libraries:" / "Programming:" etc.
        return (":" in line) and (len(line) <= 140)

    buf = ""
    for ln in lines:
        if is_probably_category(ln):
            if buf:
                out.append(buf.strip())
                buf = ""
            out.append(ln)
            continue

        # If line is very short, it is likely a wrapped word/connector
        if len(ln) <= 18 and not ln.endswith("."):
            buf = (buf + " " + ln).strip()
            continue

        # Normal line
        if buf:
            out.append((buf + " " + ln).strip())
            buf = ""
        else:
            out.append(ln)

    if buf:
        out.append(buf.strip())

    return "\n".join(out).strip()


def _skills_to_bullets(block: str) -> List[str]:
    block = _join_wrapped_lines(block)

    lines = [ln.strip() for ln in block.split("\n") if ln.strip()]

    items: List[str] = []
    for ln in lines:
        ln = ln.strip("•-– ")

        # Keep category lines as-is
        if ":" in ln and len(ln) <= 160:
            # clean spaces around punctuation
            ln = re.sub(r"\s+", " ", ln).strip()
            items.append(ln)
            continue

        # If it is a comma-separated list, split it
        if "," in ln:
            for p in [x.strip() for x in ln.split(",")]:
                p = re.sub(r"\s+", " ", p).strip()
                if 2 <= len(p) <= 60:
                    items.append(p)
        else:
            ln = re.sub(r"\s+", " ", ln).strip()
            if 3 <= len(ln) <= 90:
                items.append(ln)

    # Deduplicate and remove obvious junk tokens
    out: List[str] = []
    seen = set()
    for x in items:
        x = x.replace("\u200b", "").strip()
        if not x:
            continue
        if x in {"&", "-", "•"}:
            continue

        key = x.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(x)

    return out[:25]


def make_answer(question: str, hits: List[RetrievedChunk]) -> str:
    q = question.lower().strip()
    merged = "\n\n".join(h.text for h in hits)

    if "skill" in q:
        block = _find_skills_section(merged)
        if block:
            bullets = _skills_to_bullets(block)
            if bullets:
                return "Main skills (from the resume): " + ", ".join(f" {b}" for b in bullets)

        return (
            "I could not isolate the Technical Skills section from the retrieved chunks. "
            "Please increase top_k (for example 10) and try again."
        )

    excerpts = []
    for h in hits[:3]:
        excerpts.append(normalize_one_line(h.text)[:240])

    return "Relevant excerpts: " + ", ".join(f" {e}" for e in excerpts if e)