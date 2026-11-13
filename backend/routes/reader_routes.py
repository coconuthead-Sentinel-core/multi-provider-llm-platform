"""
reader_routes.py — Web Book Reader

Brings the desktop Book Reader's core flow into the dashboard preview:

    1. List readable files (Books/ folder + Documents fallback)
    2. Open one, return parsed text content
    3. POST a selection back as a new .md excerpt with YAML front-matter

The dashboard's "📖 Reader" tab calls these endpoints. The .md excerpts
this writes are picked up by the Library tab and by the desktop Book
Reader's Library window — same Books/ folder, same YAML schema.

MVP file types: .md, .txt, .markdown. .docx and .pdf are parsed if the
optional libraries are installed; otherwise the endpoint returns a
graceful "format-not-supported" payload so the UI can render a hint.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

# Reuse the same Books/ root the library endpoints use.
from .library_routes import BOOKS_DIR

# ── Configurable reading folders ───────────────────────────────────
# Users point the Book Reader at wherever their actual books live.
# Defaults to a few common locations on first run. Persisted to
# ~/.sentinel_forge/folders.json so it survives restarts.

USER_HOME    = Path(os.environ.get("USERPROFILE", os.path.expanduser("~")))
CONFIG_DIR   = USER_HOME / ".sentinel_forge"
FOLDERS_FILE = CONFIG_DIR / "folders.json"

DEFAULT_FOLDERS: List[Path] = [
    BOOKS_DIR,
    USER_HOME / "OneDrive" / "Documents",
    USER_HOME / "Documents",
]


def _load_folders() -> List[Path]:
    """Read the user's configured reading folders. Seeds with defaults
    on first run."""
    try:
        if FOLDERS_FILE.exists():
            raw = json.loads(FOLDERS_FILE.read_text(encoding="utf-8"))
            paths = [Path(p) for p in (raw.get("folders") or [])]
            if paths:
                return paths
    except (OSError, ValueError):
        pass
    # First run — write the defaults
    seed = [d for d in DEFAULT_FOLDERS if d.exists() and d.is_dir()]
    if not seed:
        seed = [Path.cwd()]
    _save_folders(seed)
    return seed


def _save_folders(paths: List[Path]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    FOLDERS_FILE.write_text(
        json.dumps({"folders": [str(p) for p in paths]}, indent=2),
        encoding="utf-8",
    )


def _current_folders() -> List[Path]:
    """Always returns the up-to-date list, filtered for existing dirs."""
    return [d for d in _load_folders() if d.exists() and d.is_dir()]

READABLE_EXTS = {".md", ".markdown", ".txt", ".rtf", ".html", ".htm", ".docx", ".pdf"}
TEXT_EXTS     = {".md", ".markdown", ".txt"}

reader_router = APIRouter(prefix="/reader", tags=["reader"])


# ── Optional rich-format parsers (graceful degradation) ────────────
try:
    from docx import Document  # python-docx
    HAS_DOCX = True
except Exception:               # pragma: no cover
    HAS_DOCX = False

try:
    import pypdf
    HAS_PDF = True
except Exception:               # pragma: no cover
    HAS_PDF = False

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except Exception:               # pragma: no cover
    HAS_BS4 = False


# ── Helpers ────────────────────────────────────────────────────────
def _within_allowed(path: Path) -> bool:
    """Path-traversal guard. Only allow reads under configured folders."""
    try:
        rp = path.resolve()
    except OSError:
        return False
    for root in _current_folders():
        try:
            rp.relative_to(root.resolve())
            return True
        except ValueError:
            continue
    return False


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _read_docx(path: Path) -> str:
    if not HAS_DOCX:
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED,
            "python-docx not installed. Run: pip install python-docx",
        )
    doc = Document(str(path))
    return "\n\n".join(p.text for p in doc.paragraphs if p.text)


def _read_pdf(path: Path) -> str:
    if not HAS_PDF:
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED,
            "pypdf not installed. Run: pip install pypdf",
        )
    reader = pypdf.PdfReader(str(path))
    chunks = []
    for page in reader.pages:
        try:
            chunks.append(page.extract_text() or "")
        except Exception:
            chunks.append("")
    return "\n\n".join(chunks)


def _read_html(path: Path) -> str:
    raw = _read_text(path)
    if not HAS_BS4:
        # Strip tags crudely as a fallback
        return re.sub(r"<[^>]+>", "", raw)
    soup = BeautifulSoup(raw, "html.parser")
    return soup.get_text("\n", strip=True)


def _parse_book(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in TEXT_EXTS:
        return _read_text(path)
    if ext == ".docx":
        return _read_docx(path)
    if ext == ".pdf":
        return _read_pdf(path)
    if ext in {".html", ".htm"}:
        return _read_html(path)
    if ext == ".rtf":
        # Crude RTF strip — full RTF parsing is its own library.
        raw = _read_text(path)
        return re.sub(r"\\[a-z]+-?\d* ?|[{}]", "", raw)
    raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, f"unsupported extension: {ext}")


# ── Models ─────────────────────────────────────────────────────────
class ReaderFile(BaseModel):
    name:       str
    path:       str        # absolute
    rel_path:   str        # relative to its source dir
    source_dir: str
    size:       int
    modified:   str
    ext:        str
    is_saved_excerpt: bool # True when it lives in Books/ as a saved excerpt


class ReaderListResponse(BaseModel):
    folders: List[str]
    total:   int
    items:   List[ReaderFile]


class ReaderContentResponse(BaseModel):
    name:       str
    path:       str
    ext:        str
    word_count: int
    char_count: int
    content:    str
    front_matter: Dict[str, Any] = Field(default_factory=dict)


class SaveExcerptRequest(BaseModel):
    text:          str          = Field(..., min_length=1)
    source_book:   str          = Field(default="", description="Path or name of source")
    zone:          str          = Field(default="GREEN", pattern=r"^(GREEN|YELLOW|RED)$")
    cognitive_load: int         = Field(default=7, ge=1, le=10)
    selection:     bool         = Field(default=True)
    tags:          List[str]    = Field(default_factory=list)
    title_hint:    str          = Field(default="", description="Optional short label for filename")


class SaveExcerptResponse(BaseModel):
    saved:    bool
    filename: str
    path:     str
    doc_id:   str


# ── Endpoints ──────────────────────────────────────────────────────
@reader_router.get("/list", response_model=ReaderListResponse)
async def reader_list(
    ext: Optional[str] = Query(None, description="Filter to one extension (with or without dot)"),
    limit: int = Query(500, ge=1, le=5000),
) -> ReaderListResponse:
    """List readable files across the configured reading folders."""
    wanted: Optional[str] = None
    if ext:
        wanted = ext.lower()
        if not wanted.startswith("."):
            wanted = "." + wanted

    items: List[ReaderFile] = []
    for root in _current_folders():
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            sfx = p.suffix.lower()
            if sfx not in READABLE_EXTS:
                continue
            if wanted and sfx != wanted:
                continue
            try:
                st = p.stat()
            except OSError:
                continue
            items.append(ReaderFile(
                name       = p.name,
                path       = str(p),
                rel_path   = str(p.relative_to(root)),
                source_dir = str(root),
                size       = st.st_size,
                modified   = datetime.fromtimestamp(st.st_mtime).isoformat(),
                ext        = sfx,
                is_saved_excerpt = (root.resolve() == BOOKS_DIR.resolve() and p.name.startswith("BOOKREADER-EXCERPT-")),
            ))

    items.sort(key=lambda r: r.modified, reverse=True)
    return ReaderListResponse(
        folders = [str(d) for d in _current_folders()],
        total   = len(items),
        items   = items[:limit],
    )


# ── Reading-folder management ─────────────────────────────────────
class FolderListResponse(BaseModel):
    folders: List[Dict[str, Any]]


class FolderUpdateRequest(BaseModel):
    path: str = Field(..., min_length=2, max_length=4096)


def _folder_record(p: Path) -> Dict[str, Any]:
    """Quick stats for one reading folder."""
    count = 0
    if p.exists() and p.is_dir():
        try:
            for f in p.rglob("*"):
                if f.is_file() and f.suffix.lower() in READABLE_EXTS:
                    count += 1
                    if count > 9999:
                        break
        except OSError:
            pass
    return {
        "path":   str(p),
        "exists": p.exists() and p.is_dir(),
        "count":  count,
        "is_excerpts_dir": p.resolve() == BOOKS_DIR.resolve() if p.exists() else False,
    }


@reader_router.get("/folders", response_model=FolderListResponse)
async def folders_list() -> FolderListResponse:
    """List all configured reading folders with file counts."""
    return FolderListResponse(folders=[_folder_record(p) for p in _load_folders()])


@reader_router.post("/folders", response_model=FolderListResponse)
async def folders_add(req: FolderUpdateRequest) -> FolderListResponse:
    """Add a folder to the reading list. Idempotent."""
    raw = req.path.strip().strip('"').strip("'")
    p = Path(raw).expanduser()
    if not p.exists() or not p.is_dir():
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"not a directory: {p}")
    current = _load_folders()
    if any(str(d.resolve()) == str(p.resolve()) for d in current):
        return FolderListResponse(folders=[_folder_record(d) for d in current])
    current.append(p)
    _save_folders(current)
    return FolderListResponse(folders=[_folder_record(d) for d in current])


@reader_router.delete("/folders", response_model=FolderListResponse)
async def folders_remove(path: str = Query(..., description="Absolute path to remove")) -> FolderListResponse:
    """Remove a folder from the reading list."""
    target = Path(path)
    current = _load_folders()
    kept = [d for d in current if str(d.resolve()) != str(target.resolve())]
    _save_folders(kept)
    return FolderListResponse(folders=[_folder_record(d) for d in kept])


@reader_router.get("/content", response_model=ReaderContentResponse)
async def reader_content(path: str = Query(..., description="Absolute path to the file")) -> ReaderContentResponse:
    """Parse a readable file and return its plain-text content."""
    p = Path(path)
    if not _within_allowed(p):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "path outside allowed reading folders")
    if not p.exists() or not p.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{p.name} not found")

    text = _parse_book(p)
    front_matter: Dict[str, Any] = {}
    # If it's an .md with YAML front-matter, peel it off for the UI
    from .library_routes import _parse_front_matter, _strip_front_matter
    if p.suffix.lower() in {".md", ".markdown"}:
        front_matter = _parse_front_matter(text)
        text = _strip_front_matter(text)

    return ReaderContentResponse(
        name       = p.name,
        path       = str(p),
        ext        = p.suffix.lower(),
        word_count = len(text.split()),
        char_count = len(text),
        content    = text,
        front_matter = front_matter,
    )


_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9_\-]+")


def _slugify(s: str, default: str = "excerpt") -> str:
    s = _SAFE_FILENAME_RE.sub("_", s.strip())[:60].strip("_")
    return s or default


@reader_router.post("/save-excerpt", response_model=SaveExcerptResponse)
async def reader_save_excerpt(req: SaveExcerptRequest) -> SaveExcerptResponse:
    """Save selected text to Books/ as a new .md excerpt with YAML front-matter.

    Schema matches what the desktop Book Reader writes, so the file
    shows up in /api/library/excerpts (and in the desktop Library
    window) immediately.
    """
    BOOKS_DIR.mkdir(parents=True, exist_ok=True)

    ts_dt   = datetime.now(timezone.utc).astimezone()
    ts_iso  = ts_dt.replace(microsecond=0).isoformat(timespec="seconds")
    ts_safe = ts_iso.replace(":", "-").replace("+", "_")

    # Build a doc_id and filename
    src_stem = ""
    if req.source_book:
        src_stem = _slugify(Path(req.source_book).stem, "source")[:30]
    elif req.title_hint:
        src_stem = _slugify(req.title_hint, "excerpt")[:30]
    else:
        src_stem = "web"

    doc_id   = f"BOOKREADER-EXCERPT-{src_stem}_{ts_safe}_v001"
    filename = f"{doc_id}.md"
    path     = BOOKS_DIR / filename

    # Avoid clobber — append _v002, _v003, ...
    n = 2
    while path.exists():
        filename = f"{doc_id}_v{n:03}.md"
        path     = BOOKS_DIR / filename
        n += 1

    body  = req.text.strip()
    words = len(body.split())
    tags_yaml = "[]" if not req.tags else "[" + ", ".join(f'"{t}"' for t in req.tags) + "]"

    front = (
        "---\n"
        f"doc_id: {doc_id}\n"
        f"zone: {req.zone}\n"
        f"cognitive_load: {req.cognitive_load}\n"
        f'source_book: "{req.source_book}"\n'
        f"timestamp: {ts_iso}\n"
        f"selection: {'true' if req.selection else 'false'}\n"
        f"word_count: {words}\n"
        f"tags: {tags_yaml}\n"
        "saved_via: web-reader\n"
        "---\n\n"
    )

    title = req.title_hint.strip() or f"Saved {ts_iso[:16].replace('T',' ')} — web reader"
    header = (
        f"# {title}\n\n"
        f"- Saved: {ts_iso}\n"
        f"- Source: {req.source_book or '(unspecified)'}\n"
        f"- Word count: {words}\n\n---\n\n"
    )

    path.write_text(front + header + body + "\n", encoding="utf-8")

    return SaveExcerptResponse(
        saved    = True,
        filename = filename,
        path     = str(path),
        doc_id   = doc_id,
    )
