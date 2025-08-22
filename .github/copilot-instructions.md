# Copilot Agent Onboarding Guide

Trust this document first. Only search the codebase if something here is missing or demonstrably wrong.

## 1. Repository Summary
Lightweight local web chat UI (Flask) that lets a user converse with AI models from different providers (currently OpenAI & Gemini) and switch model/provider mid‑conversation. Persists chats/messages in a local SQLite database (`instance/omni_chat.db`). Exposes REST + SSE streaming endpoints; frontend is plain HTML/JS templates + tailwind. Tests fully mock external API calls so the suite runs offline. Always run `source .venv/bin/activate` before executing other code.

## 1.1 Main Files
- app.py: primary file with all endpoints
- chat.py: logic to do API calls / streaming
- database.py: database logic (sqlite)
- templates/index.html: primary frontend file
- static/providers.json: supported LLM providers/models and favorites

## 2. Tech Stack & Footprint
- Language: Python 3.12 (README says 3.10+, tests pass on 3.12.3). Venv in `.venv`
- Framework: Flask 3.x.
- Data: SQLite (file path set via `app.config['DATABASE']`).
- Env/config: `.env` (API keys) loaded with `python-dotenv`.
- Runtime deps: `requirements.txt` (runtime only).
- Dev/Test deps: `requirements-dev.txt` (includes `-r requirements.txt` plus pytest, black, flake8, mypy, pytest-cov, pre-commit).
- Size: Single small service (< 15 Python source/test modules). No compiled steps.

## 3. High-Confidence Command Recipes
Always run these inside the project root with the virtual environment activated. Order matters where stated.

### 3.1 Bootstrap (one time per clone)
Pick runtime-only or full dev setup.
Runtime only (just to run the app):
```bash
python3 -m venv .venv          # Takes ~3 seconds
source .venv/bin/activate
pip install -r requirements.txt  # Takes ~15-20 seconds
```
Full dev (recommended for contributing):
```bash
python3 -m venv .venv          # Takes ~3 seconds  
source .venv/bin/activate
pip install -r requirements-dev.txt  # Takes ~30-40 seconds. NEVER CANCEL: Set timeout to 120+ seconds.
```
Idempotent: re-running the same pip install is safe. Do not upgrade packages arbitrarily; tests validated against current spec.

### 3.2 Run Application (dev)
Always activate the venv before running any commands.
```bash
source .venv/bin/activate  # if not already
python app.py              # Takes ~3 seconds to start. App runs on http://127.0.0.1:5000
```
Optional: set API keys beforehand (see §6) or through UI settings.

### 3.3 Test Suite
Requires dev deps installed (`requirements-dev.txt`). Always activate the venv before other commands
```bash
source .venv/bin/activate
pip install -r requirements-dev.txt  # safe if already installed
pytest -q                  # Takes ~3 seconds total. NEVER CANCEL: Set timeout to 60+ seconds for safety.
```
All tests (70) should pass in ~1 second (observed: 0.85s). They create a temp SQLite DB & .env per test; no network calls. A failure usually signals interface drift—fix before commit.

### 3.4 Lint / Format / Type Check (recommended before PRs)
Install dev deps first. Then:
```bash
black --check .            # Takes ~1 second. Use `black .` to auto-format
mypy .                     # Takes ~15 seconds. NEVER CANCEL: Set timeout to 60+ seconds.
```
Note: mypy currently shows some type errors in chat.py (OpenAI API overload variants). These are non-blocking - tests pass and app functions correctly.

### 3.5 Clean
Safe cleanup targets:
```bash
rm -rf __pycache__ tests/__pycache__ .pytest_cache .mypy_cache  # Takes <1 second
```
WARNING: Do NOT delete `instance/omni_chat.db` unless you want to lose chat history. The DB will be recreated automatically on next app start but you'll lose all chats.

## 4. Architectural Layout
Top-level Python modules (no packages):
- `app.py`: Flask app factory + route/endpoints. Defines REST JSON endpoints for chats, streaming SSE endpoint, CRUD operations for chats, and API key management endpoints.
- `chat.py`: Provider abstraction. Wraps OpenAI & Gemini SDK calls. Provides synchronous (`generate_reply`) and streaming (`generate_reply_stream`) interfaces returning dataclasses (`ChatReply`, `StreamChunk`). Handles reasoning model special case (OpenAI o3*) and mocking in tests.
- `database.py`: SQLite access layer: initialization, lightweight migration, CRUD helpers for chats/messages.

Frontend:
- `templates/index.html` & `templates/base.html`: UI layout, form, provider/model selectors.
- `static/providers.json`: Declares available providers/models for UI.

Persistence:
- SQLite file at `instance/omni_chat.db` (auto-created). Tests should use a temp path, never affect prod db.

Environment:
- `.env` path configurable via `app.config['ENV_PATH']`. API keys: `OPENAI_API_KEY`, `GEMINI_API_KEY`.

## 5. Key Code Paths
High-value functions you might extend:
- `create_app()` (in `app.py`) – add new routes or config.
- `/api/chat` & `/api/chat/stream` – main chat logic; maintain validation sequence: extract JSON, `_validate_chat_request`, create/update chat, persist user message, call generation, persist assistant message, build response.
- `generate_reply` / `generate_reply_stream` – extend to support new providers; follow existing pattern: fetch API key, short-circuit with error chunk if absent.
- Database helpers (in `database.py`) – keep timestamps UTC ISO format; always call `commit()` after write operations (already handled in routes).

## 6. API Keys & Env Handling
Set via UI or environment file (.env). Programmatic examples:
```bash
echo 'OPENAI_API_KEY=sk-your-key' >> .env
echo 'GEMINI_API_KEY=your-gemini-key' >> .env
```
App auto-loads .env on startup and on key update endpoints. Missing keys yield structured JSON errors (`missing_key_for`). Do not hardcode secrets in code or tests (tests intentionally mock keys as `PUT_API_KEY_HERE`).

## 7. Testing Strategy & Expectations
- All external calls are neutralized by fixtures in `tests/conftest.py` (monkeypatching `_get_api_key` + provider SDK objects). Avoid introducing logic that directly imports provider clients at module import time beyond existing patterns; lazy initialization helps keep tests isolated.
- Each test gets unique temp DB & .env; never rely on cross-test state.
- When adding new provider logic, add tests following existing style: simulate missing key (expect error path) & normal reply (can echo input if SDK missing).

## 8. Extending the System
Add provider: implement call + streaming functions (mirroring `_openai_call` / `_openai_call_stream`), branch in `generate_reply*`, update `static/providers.json`, supply API key name mapping, add tests for missing key & basic flow.
Add chat metadata: modify `chats` table (write migration or extend `_ensure_message_columns_exist` pattern) and adjust serialization in routes `/api/chats` & `/api/chats/<id>`.
Add linting/CI: create GitHub Actions workflow (e.g., run `pip install -r requirements.txt && pytest -q && mypy .`).

## 9. Common Pitfalls & Guard Rails
- Always install requirements before running tests; missing SDK imports are tolerated (graceful), but base libs (Flask, pytest) are required.
- Do not assume network access in tests—never assert on real provider output.
- Keep response JSON stable: tests expect specific keys (`error`, `missing_key_for`, `reply`, `chat_id`). Avoid renaming without updating tests.
- Ensure new DB writes are followed by `commit()`. Streaming path commits incrementally.
- Validation: maintain order & error messages: "message is required", "provider is required", "model is required" for missing inputs (tests assert exact strings).

## 10. Manual Validation Checklist (Pre-PR)
**CRITICAL**: Always validate changes with complete user scenarios. Simply starting/stopping the app is NOT sufficient.

### 10.1 Basic Commands Validation
0. `source .venv/bin/activate` (always activate venv first)
1. `pip install -r requirements-dev.txt` (or ensure already installed). **Timeout: 120+ seconds**
2. `pytest -q` (expect all green: 70 tests). **Timeout: 60+ seconds**
3. `mypy . && black --check .` (address format issues with `black .` first). **Timeout: 60+ seconds**
4. Verify DB present or created (`instance/omni_chat.db`) after running app.

### 10.2 Manual UI Testing (REQUIRED)
**Always run these UI validation scenarios after making changes:**

1. **Start Application**: `python app.py` - verify starts without errors
2. **Load UI**: Navigate to http://127.0.0.1:5000 - verify page loads with:
   - Provider/model selector dropdowns visible
   - Chat input area present  
   - History sidebar shows "No previous chats yet"
3. **Test Missing API Key Flow**:
   - Type a test message and send
   - Verify error message appears: "[provider] API key not set"
   - Verify settings modal opens automatically
   - Take screenshot to verify UI state
4. **Test Provider Switching**:
   - Switch between OpenAI and Gemini providers
   - Verify model dropdown updates correctly for each provider
   - Verify model configuration panel updates with provider-specific parameters
5. **Test Settings Modal**:
   - Click settings button (⚙️)
   - Verify API key input fields are present
   - Test Close button functionality
6. **Test Chat History**: 
   - Verify new chat appears in sidebar after sending message
   - Verify chat title updates properly

### 10.3 Database Validation
- Verify `instance/omni_chat.db` is created after first chat
- Do NOT delete this file unless intentionally resetting chat history

### 10.4 Screenshot Documentation
When making UI changes, **always take screenshots** using browser automation to show:
- Before and after states of changes
- Error states (missing API keys, etc.)
- New functionality working correctly

## 11. File Inventory (Root)
- `app.py`, `chat.py`, `database.py`
- `requirements.txt` (runtime) / `requirements-dev.txt` (dev/test)
- `README.md`, `LICENSE`
- `templates/`, `static/`, `tests/`, `.gitignore`
- `.github/copilot-instructions.md` (this file)
No pyproject.toml / setup.cfg / CI workflows yet.

## 12. When to Search
Only search if: adding an unfamiliar provider, altering persistence schema, or if a test fails and the reason is not covered here. Otherwise rely on these instructions to avoid redundant exploration.

---
Follow these guidelines to minimize iteration time and avoid avoidable build/test failures. Trust them first.