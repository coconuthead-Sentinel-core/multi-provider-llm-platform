"""
library_routes.py — Book Reader Library integration

Reads the Sentinel Forge book-reader's library folder (Desktop\\Books\\),
parses YAML front-matter on each saved excerpt, and exposes it as JSON
to the dashboard. This is the wire-up between the desktop book reader
and the full-stack dashboard:

    Book Reader (Tk app, writes .md files)  ─┐
                                              ├──> Dashboard renders saves
    /api/library/* endpoints (this file)    ──┘    with zone / load / source

No new dependencies — front-matter is parsed with a small built-in parser.
"""
from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, status, Body
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

# Where the book reader writes saves. Override with env var if needed.
DEFAULT_BOOKS_DIR = os.path.join(
    os.environ.get("USERPROFILE", os.path.expanduser("~")),
    "OneDrive", "Desktop", "Books",
)
BOOKS_DIR = Path(os.environ.get("SENTINEL_FORGE_BOOKS_DIR", DEFAULT_BOOKS_DIR))

library_router = APIRouter(prefix="/library", tags=["library"])


# ── Front-matter parser ────────────────────────────────────────────
_FRONT_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_front_matter(text: str) -> Dict[str, Any]:
    """Tiny YAML-ish parser tailored to the book reader's schema.

    Handles `key: value` pairs, quoted strings, integers, and the
    empty-list form `tags: []`. Good enough — keeps us off PyYAML.
    """
    m = _FRONT_RE.match(text)
    if not m:
        return {}
    meta: Dict[str, Any] = {}
    for line in m.group(1).splitlines():
        line = line.rstrip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, raw = line.partition(":")
        key = key.strip()
        raw = raw.strip()
        if not raw:
            meta[key] = ""
            continue
        # Strip surrounding quotes
        if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
            meta[key] = raw[1:-1]
            continue
        # Empty list
        if raw == "[]":
            meta[key] = []
            continue
        # Integer
        try:
            meta[key] = int(raw)
            continue
        except ValueError:
            pass
        meta[key] = raw
    return meta


def _strip_front_matter(text: str) -> str:
    m = _FRONT_RE.match(text)
    return text[m.end():] if m else text


def _safe_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _excerpt_record(path: Path, include_body: bool = False) -> Dict[str, Any]:
    """Build the JSON record for one saved excerpt."""
    text = _safe_read(path)
    meta = _parse_front_matter(text)
    body = _strip_front_matter(text)
    rec: Dict[str, Any] = {
        "filename":       path.name,
        "doc_id":         meta.get("doc_id", path.stem),
        "zone":           meta.get("zone", "GREEN"),
        "cognitive_load": meta.get("cognitive_load", 0),
        "source_book":    meta.get("source_book", ""),
        "timestamp":      meta.get("timestamp", ""),
        "selection":      str(meta.get("selection", "")).lower() == "true",
        "word_count":     meta.get("word_count", len(body.split())),
        "tags":           meta.get("tags", []) if isinstance(meta.get("tags"), list) else [],
        "size_bytes":     path.stat().st_size if path.exists() else 0,
        "mtime":          datetime.fromtimestamp(path.stat().st_mtime).isoformat() if path.exists() else "",
        "preview":        body.strip().split("\n\n", 1)[0][:280] if body else "",
    }
    if include_body:
        rec["body"] = body
    return rec


def _scan_books_dir() -> List[Dict[str, Any]]:
    if not BOOKS_DIR.exists() or not BOOKS_DIR.is_dir():
        return []
    out = []
    for p in BOOKS_DIR.iterdir():
        if p.is_file() and p.suffix.lower() == ".md" and not p.name.startswith("_"):
            try:
                out.append(_excerpt_record(p, include_body=False))
            except Exception:
                continue
    # Newest first
    out.sort(key=lambda r: r.get("mtime", ""), reverse=True)
    return out


# ── Endpoints ──────────────────────────────────────────────────────
@library_router.get("/stats")
async def library_stats() -> Dict[str, Any]:
    """Aggregate stats over the book reader's library folder."""
    items = _scan_books_dir()
    by_zone = {"GREEN": 0, "YELLOW": 0, "RED": 0}
    by_source: Dict[str, int] = {}
    total_words = 0
    load_sum = 0
    load_n = 0
    for it in items:
        z = it.get("zone") or "GREEN"
        if z in by_zone:
            by_zone[z] += 1
        src = (it.get("source_book") or "unknown")
        src_label = os.path.basename(src) if src else "unknown"
        by_source[src_label] = by_source.get(src_label, 0) + 1
        try:
            total_words += int(it.get("word_count") or 0)
        except (TypeError, ValueError):
            pass
        try:
            load_sum += int(it.get("cognitive_load") or 0)
            load_n += 1
        except (TypeError, ValueError):
            pass
    avg_load = (load_sum / load_n) if load_n else 0.0
    return {
        "books_dir":    str(BOOKS_DIR),
        "exists":       BOOKS_DIR.exists(),
        "total_saves":  len(items),
        "by_zone":      by_zone,
        "by_source":    by_source,
        "total_words":  total_words,
        "avg_load":     round(avg_load, 2),
        "latest_save":  items[0]["mtime"] if items else "",
    }


@library_router.get("/excerpts")
async def library_excerpts(
    zone: Optional[str] = Query(None, description="Filter: GREEN / YELLOW / RED"),
    source: Optional[str] = Query(None, description="Substring match against source_book"),
    limit: int = Query(200, ge=1, le=2000),
) -> Dict[str, Any]:
    """List excerpts saved by the book reader, newest first."""
    items = _scan_books_dir()
    if zone:
        zu = zone.upper()
        items = [i for i in items if (i.get("zone") or "").upper() == zu]
    if source:
        items = [i for i in items if source.lower() in (i.get("source_book") or "").lower()]
    return {
        "books_dir": str(BOOKS_DIR),
        "count":     len(items),
        "items":     items[:limit],
    }


@library_router.get("/excerpt/{filename}")
async def library_excerpt(filename: str) -> Dict[str, Any]:
    """Return one excerpt's full body + metadata."""
    # Guard against path traversal — only allow simple filenames
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid filename")
    p = BOOKS_DIR / filename
    if not p.exists() or not p.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{filename} not found")
    return _excerpt_record(p, include_body=True)


@library_router.get("/excerpt/{filename}/raw", response_class=PlainTextResponse)
async def library_excerpt_raw(filename: str) -> str:
    """Return one excerpt's raw markdown source (front-matter included)."""
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid filename")
    p = BOOKS_DIR / filename
    if not p.exists() or not p.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{filename} not found")
    return _safe_read(p)


# ── ASK YOUR LIBRARY ───────────────────────────────────────────────
# Cross-excerpt search. Scores every save against the question using
# weighted keyword overlap on title + body. This is the platform-only
# feature: the standalone book reader can search inside one file at a
# time; the platform searches across everything you've ever saved.

class AskRequest(BaseModel):
    question:  str = Field(..., min_length=2, max_length=500)
    zone:      Optional[str] = None    # restrict to GREEN/YELLOW/RED
    top_k:     int = Field(5, ge=1, le=20)


class AskMatch(BaseModel):
    filename:       str
    doc_id:         str
    zone:           str
    cognitive_load: int
    source_book:    str
    word_count:     int
    score:          float
    snippet:        str
    hits:           List[str]          # which terms matched


class AskResponse(BaseModel):
    question: str
    books_dir: str
    total_searched: int
    matched: int
    answer_synthesis: str               # cheap stitched-together summary
    matches: List[AskMatch]


_STOPWORDS = {
    "the","a","an","and","or","but","is","are","was","were","be","been","being",
    "of","in","on","at","to","for","with","by","from","as","that","this","these",
    "those","it","its","i","you","he","she","we","they","do","does","did","have",
    "has","had","not","no","so","if","then","than","what","which","who","whom",
    "how","why","when","where","can","could","should","would","may","might","will",
}


def _tokenize(text: str) -> List[str]:
    return [t for t in re.findall(r"[a-zA-Z][a-zA-Z\-']{1,}", text.lower()) if t not in _STOPWORDS]


def _best_snippet(body: str, terms: List[str], width: int = 220) -> str:
    """Find the body chunk with the most query-term hits and return it."""
    if not body or not terms:
        return body[:width]
    text = body.replace("\r", "")
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    best = ("", -1)
    lowered_terms = [t.lower() for t in terms]
    for p in paras:
        low = p.lower()
        score = sum(low.count(t) for t in lowered_terms)
        if score > best[1]:
            best = (p, score)
    snip = best[0] or text[:width]
    if len(snip) > width:
        # try to center on first match
        first_idx = -1
        low = snip.lower()
        for t in lowered_terms:
            i = low.find(t)
            if i >= 0 and (first_idx < 0 or i < first_idx):
                first_idx = i
        if first_idx >= 0:
            start = max(0, first_idx - width // 3)
            snip = ("…" if start > 0 else "") + snip[start:start + width] + ("…" if start + width < len(snip) else "")
        else:
            snip = snip[:width] + "…"
    return snip


@library_router.post("/ask", response_model=AskResponse)
async def library_ask(req: AskRequest) -> AskResponse:
    """Search across every saved excerpt for the best matches to a question.

    Scoring: TF-style sum of query-term occurrences across body + title,
    with a small boost for title hits. Stop words are ignored. Returns
    the top-K matches with a snippet centered on the first hit, plus a
    short stitched 'answer_synthesis' for quick scanning.
    """
    q_terms = _tokenize(req.question)
    if not q_terms:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "question contained no searchable terms")

    items_full: List[Dict[str, Any]] = []
    if BOOKS_DIR.exists():
        for p in BOOKS_DIR.iterdir():
            if not (p.is_file() and p.suffix.lower() == ".md" and not p.name.startswith("_")):
                continue
            text = _safe_read(p)
            meta = _parse_front_matter(text)
            if req.zone and (meta.get("zone") or "").upper() != req.zone.upper():
                continue
            body = _strip_front_matter(text)
            items_full.append({"path": p, "meta": meta, "body": body})

    scored: List[Dict[str, Any]] = []
    for it in items_full:
        body_low = it["body"].lower()
        title_low = (it["meta"].get("source_book") or "").lower() + " " + str(it["meta"].get("doc_id") or "").lower()
        hits_here: List[str] = []
        score = 0.0
        for t in q_terms:
            b = body_low.count(t)
            h = title_low.count(t)
            if b or h:
                hits_here.append(t)
                score += b + 3.0 * h     # title hits worth more
        # Length normalization (favor concentration over sheer length)
        norm = max(1.0, (len(body_low.split()) or 1) / 200.0)
        score = score / norm
        if score > 0:
            scored.append({**it, "score": score, "hits": hits_here})

    scored.sort(key=lambda r: r["score"], reverse=True)
    top = scored[: req.top_k]

    matches: List[AskMatch] = []
    for r in top:
        meta = r["meta"]
        matches.append(AskMatch(
            filename       = r["path"].name,
            doc_id         = str(meta.get("doc_id") or r["path"].stem),
            zone           = str(meta.get("zone") or "GREEN"),
            cognitive_load = int(meta.get("cognitive_load") or 0),
            source_book    = str(meta.get("source_book") or ""),
            word_count     = int(meta.get("word_count") or 0),
            score          = round(float(r["score"]), 3),
            snippet        = _best_snippet(r["body"], r["hits"]),
            hits           = r["hits"],
        ))

    if matches:
        sources = sorted({os.path.basename(m.source_book) or "unknown" for m in matches})
        synth = (
            f"Found {len(matches)} relevant excerpt(s) across "
            f"{len(sources)} source(s): {', '.join(sources)}. "
            f"Top match scored {matches[0].score} on terms: {', '.join(matches[0].hits)}."
        )
    else:
        synth = "No saved excerpts mention those terms. Try a broader question, or save more from your books."

    return AskResponse(
        question          = req.question,
        books_dir         = str(BOOKS_DIR),
        total_searched    = len(items_full),
        matched           = len(scored),
        answer_synthesis  = synth,
        matches           = matches,
    )
