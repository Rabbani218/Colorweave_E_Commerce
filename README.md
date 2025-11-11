# ColorWeave — AI‑Powered E‑Commerce

ColorWeave is a modern Flask e‑commerce app upgraded into a full‑stack AI experience: semantic search, an in‑page AI shopping assistant, personalized and hybrid recommendations, and lightweight visual search. All AI runs locally by default (no external API keys required), with optional upgrades if you install heavier models.

## Highlights
- AI Assistant: floating chat widget that answers catalog questions with retrieval‑augmented responses.
- Semantic Search: query products with meaning, not just keywords.
- Recommendations:
	- Content‑based (embedding similarity)
	- Collaborative filtering (co‑occurrence)
	- Hybrid ranking
	- Personalized via user/session events
- Visual Search: upload an image and find similar items via lightweight RGB histograms.
- Admin Analytics: simple dashboard of views and add‑to‑cart events.
- Security & Ops: CORS, security headers, rate limiting + audit logs, health check.

## Quick Start (Windows / PowerShell)
1) Create a virtual environment and install deps

```powershell
python -m venv venv
./venv/Scripts/Activate.ps1
pip install -r requirements.txt
```

2) Run the app (defaults to http://127.0.0.1:5001)

```powershell
python app.py
```

Optional environment variables:
- HOST: interface to bind (default: 127.0.0.1)
- PORT or FLASK_RUN_PORT: port (default: 5001)
- DEBUG or FLASK_DEBUG: enable reloader and debug logs (default: false)
- ADMIN_PASSWORD: seed an admin user on first run
- APPLY_MIGRATIONS: run Alembic upgrade at startup (default: false)
- AI_WARM: warm embedding and vision indices on startup (default: true)
- CORS_ORIGINS: allowed origins for /api/* (default: "*")

Then open http://127.0.0.1:5001/ in your browser.

## Running with Docker Compose (optional)

```powershell
docker-compose up --build
```

This starts Redis and the Flask app, wiring server‑side sessions automatically. Without Docker, the app falls back to filesystem sessions.

## AI Endpoints
- GET `/api/ai/search?q=...` — semantic product search
- GET `/api/ai/recommend?product_id=<id>` — content‑based similar items
- GET `/api/ai/recommend_cf?product_id=<id>` — co‑occurrence CF
- GET `/api/ai/recommend_hybrid?product_id=<id>` — hybrid ranking
- GET `/api/ai/recommend_for_user?session_id=<sid>` — personalized list
- POST `/api/ai/visual_search` — multipart form upload of an image
- POST `/api/ai/chat` — assistant chat

### Chat Assistant Reply Variation
The `/api/ai/chat` endpoint now produces varied, customer‑service style responses:
- Lightweight intent detection (price, color, type, greeting, recommend, general)
- Randomized friendly openers and follow‑ups for a less repetitive feel
- Retrieval‑augmented suggestions (top 3 shown in message, full list returned in `suggestions`)

Example request:
```json
{ "message": "halo rekomendasi gelang biru murah" }
```
Example response (reply text varies per call):
```json
{
	"reply": "Siap, aku cekkan untukmu. Dari yang relevan, beberapa opsi terjangkau adalah: ColorWeave Bracelet, ColorWeave Bracelet + Manik Manik, Minimalist ColorWeave. Kalau mau, aku bisa tampilkan lebih banyak opsi serupa.",
	"suggestions": [ {"id":1,"name":"ColorWeave Bracelet","price":5000,"image":"bracelet1.svg"}, ... ]
}
```
No external LLM dependency; variation is template‑based for speed & privacy.

Notes:
- Embeddings use a tiered approach: TF‑IDF fallback (no extra deps) → scikit‑learn TF‑IDF → sentence‑transformers if installed.
- Vision search uses Pillow only; features cached under `data/ai_index/`.

## Features & Architecture
- Backend: Flask, SQLAlchemy, Flask‑Login, Flask‑Session, Flask‑Migrate
- Data: SQLite by default (`instance/`), JSON seed at `data/products.json`
- Templates: Jinja with Bootstrap, global AI widget in `templates/base.html`
- AI Modules: `app/ai/embeddings.py`, `app/ai/recommender.py`, `app/ai/vision.py`
- Security: security headers, simple per‑process rate limiting, audit logs
- Health: `/health` endpoint for uptime checks

## Development

### Tests
```powershell
pytest -q
```

### Database (Flask‑Migrate)
```powershell
$env:FLASK_APP = "app.py"
flask db upgrade

# After model changes
flask db migrate -m "your message"
flask db upgrade
```

### Admin
- Login at `/admin/login`
- Default admin password via `ADMIN_PASSWORD` on first run (e.g., `adminpass`)
- Upload product images to `static/images/`

## Data & Assets
- Products live in `data/products.json`. Example item:

```json
{
	"id": 1,
	"name": "ColorWeave Bracelet",
	"price": 5000,
	"description": "...",
	"image": "Bracelet1.jpg",
	"stock": 20
}
```

Put images in `static/images/` and reference the filename in `image`.

## Project Structure (partial)
- `app.py` — starter (env‑driven host/port/debug, optional migrations, AI warmup)
- `app/` — Flask application package
	- `__init__.py` — factory, extensions, blueprints, security headers, health
	- `models.py` — SQLAlchemy models (tz‑aware events)
	- `routes.py` — shop routes (products, cart)
	- `admin.py` — admin panel + analytics
	- `ai/` — embeddings, vision, recommender, AI API routes
- `templates/` — Jinja templates
- `static/` — assets
- `data/` — initial products and AI caches
- `migrations/` — Alembic migrations (optional)

## Roadmap
- Stronger CSP (nonces, removal of inline scripts)
- Redis‑backed rate limiting for multi‑instance deployments
- Richer analytics charts and time filters
- Optional heavier models when allowed (sentence‑transformers)

## UI Updates (Recent)
- Improved dark mode readability (higher contrast form inputs & assistant panel placeholders)
- Sticky footer (removed bottom whitespace, footer anchors to page end)
- Minor assistant input styling enhancements
- **Products Page Redesign:**
  - Unified search interface with tabs (text search / image search in one box)
  - Added quick filter buttons for popular colors and styles
  - Enhanced visual hierarchy with improved spacing and animations
  - Created 10+ new bracelet product images with various colors and themes
  - Expanded product catalog from 3 to 13 items with diverse price points
  - Improved product card hover effects and transitions

## Accounts and Admin (New)
- Profile avatars: upload an image on `/profile` (PNG/JPG/JPEG/GIF/WEBP). The navbar shows a circular avatar; when missing, a neutral placeholder is used.
- Flash messages: now stick under the navbar and won’t overlap the assistant or page content.
- Admin access:
	- Regular link now points to `/admin/login` unless you’re already an admin.
	- Optional dev shortcut: set `ALLOW_DEV_ADMIN=1` and visit `/dev/make_admin` while logged in to elevate your current account for local testing.
