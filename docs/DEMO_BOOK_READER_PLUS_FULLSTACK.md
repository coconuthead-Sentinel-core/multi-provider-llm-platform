# Demo — Book Reader × Full Stack Integration

**Author:** Shannon Brian Kelly
**Date:** 2026-05-21
**Audience:** anyone you're showing this to (recruiters, collaborators, you yourself)

---

## The pitch in one sentence

> The Sentinel Forge **desktop book reader** and the Sentinel Forge **FastAPI dashboard** share a single library on disk. Save an excerpt in the desktop app — it appears in the web dashboard in real time, classified by zone, cognitive load, source book, and word count.

This is the positive result the integration delivers: **one workflow, two surfaces, zero copy-paste.**

---

## What's wired together

```
┌────────────────────────┐                  ┌─────────────────────────────┐
│   📖 Book Reader       │                  │   📊 Sentinel Forge          │
│   (Tk desktop app)     │                  │      Dashboard (web UI)      │
│                        │   shared disk    │                              │
│   • Read books         │   ─────────►     │   • Library panel            │
│   • Highlight passages │   Desktop\Books\ │   • Zone breakdown           │
│   • Save excerpts      │   *.md + YAML    │   • Source-book grouping     │
│   • Tag zone + load    │                  │   • Live preview             │
└────────────────────────┘                  └─────────────────────────────┘
        │                                              ▲
        └──────── writes ──────► .md files ──── reads ─┘
                                 (front-matter)
                                       │
                                       ▼
                            ┌─────────────────────────┐
                            │  FastAPI                │
                            │  /api/library/stats     │
                            │  /api/library/excerpts  │
                            │  /api/library/excerpt/. │
                            └─────────────────────────┘
```

**The contract** — every `.md` file the book reader saves carries this header:

```yaml
---
doc_id: BOOKREADER-EXCERPT-<source>_<timestamp>_v001
zone: GREEN | YELLOW | RED
cognitive_load: 1-10
source_book: <full path>
timestamp: 2026-05-21T18:48:54
word_count: 8681
tags: []
---
```

The FastAPI backend parses that header and surfaces it to the dashboard.

---

## The 60-second demo

### 1. Start the dashboard
Double-click **Sentinel Forge Dashboard** on the Desktop.
The FastAPI backend starts hidden; the browser opens to the dashboard.

### 2. Click "📚 Book Library" in the left nav
You see:
- **Stats strip:** total saves, GREEN / YELLOW / RED counts, total words, avg cognitive load
- **Saves list:** every excerpt you've ever clicked Save on, newest first
- **By source book:** which books you've drawn the most from

### 3. Open the Book Reader
Double-click **Book Reader** on the Desktop. Open a book. Highlight a paragraph. Click **💾 Save**.

### 4. Back in the dashboard
Click **⟳ Refresh** in the Library panel.
The new excerpt is already there — same zone, same word count, click to preview.

**That's the result.** No upload step, no copy-paste, no second sync tool. The desktop app writes; the dashboard reads.

---

## Why this matters (the "positive result" story)

| Without the integration | With the integration |
|---|---|
| Saves disappear into a folder you forget about | Saves surface as live dashboard cards |
| No sense of what you've collected over time | Zone breakdown shows what's active vs. archived |
| Can't see patterns across books | Source breakdown shows where your attention is concentrated |
| One-off app, no portfolio story | Demonstrable end-to-end stack: desktop → file → API → web |

This is what makes it a **real workflow** — not two unrelated apps that happen to share a folder name.

---

## How it was built (implementation strategy)

The design choice was *file system as integration surface* — no message queue, no shared database, no IPC.

**Why:** The book reader was designed standalone ("No browser, no web server, no API, no internet" — see `book_reader.py:5`). Forcing it to make HTTP calls would defeat its offline-first design. Instead the FastAPI layer treats `Desktop\Books\` as a read-only library and serves *projections* of it as JSON.

**The cost:** the dashboard is read-only against the library (no write-back yet). That's a deliberate scope choice — easy to add later.

**The wins:**
1. **Loose coupling.** Book reader doesn't know the FastAPI exists. FastAPI doesn't know which app wrote the files.
2. **Resilience.** Server can be off. Book reader still works. Files stay portable.
3. **Inspectability.** Every save is a plain `.md` you can open in Notepad. No opaque blob storage.
4. **Demo-readiness.** New save shows up on next refresh. Visible cause and effect.

---

## What was built today (touchpoints)

| What | Where |
|---|---|
| FastAPI library routes | `backend/routes/library_routes.py` |
| Route registration | `main.py` (added two lines) |
| Dashboard "Book Library" tab | `frontend/dashboard.html` (Alpine.js panel) |
| Silent launcher | `launch_sentinel_forge.vbs` |
| Shortcut installer | `install_dashboard_shortcut.ps1` |
| Custom dashboard icon | `dashboard.ico` |
| Desktop shortcut | `Desktop\Sentinel Forge Dashboard.lnk` |

---

## Run-from-scratch checklist

If you wipe the machine and want to reproduce:

```powershell
# 1. Clone or copy this project somewhere stable
cd "$env:USERPROFILE\OneDrive\Desktop\Claude AI\Completed projects\Sentinel-of-sentinel-s-Forge"

# 2. Install backend deps (uvicorn, fastapi, pydantic, etc.)
py -3 -m pip install -r requirements.txt

# 3. Drop the desktop shortcut
powershell -ExecutionPolicy Bypass -File install_dashboard_shortcut.ps1

# 4. (Optional) Install the book reader if it isn't there yet
#    The book reader's own scripts/install_book_reader_shortcut.ps1
#    drops the "Book Reader" icon on the Desktop.

# 5. Double-click "Sentinel Forge Dashboard" — done.
```

If the `Books\` folder lives somewhere else, set `SENTINEL_FORGE_BOOKS_DIR` before starting the server.

---

## Endpoints (for anyone curious)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/library/stats` | Total saves, zone breakdown, source breakdown, avg load |
| GET | `/api/library/excerpts?zone=GREEN&source=A2` | List excerpts, newest first |
| GET | `/api/library/excerpt/{filename}` | One excerpt + full body |
| GET | `/api/library/excerpt/{filename}/raw` | Raw markdown with front-matter |

All four are listed in Swagger at `http://127.0.0.1:8000/docs` under the **library** tag.
