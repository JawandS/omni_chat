# Omni Chat

A modular Flask web app that provides a clean, modern chat interface (like ChatGPT/Gemini) and lets users switch between multiple model providers (OpenAI, Anthropic, Google Gemini). Stores chat history and user-provided API keys securely (encrypted) in SQLite. Tailwind is used for styling, with a techy blue default theme and theme switching.

## Features
- Flask backend with Blueprints and clean structure
- Providers: OpenAI (Chat Completions), Anthropic (Claude), Google Gemini (Generative AI)
- SQLite persistence for chat sessions and messages
- Encrypted API key storage using Fernet
- Tailwind UI with modern, responsive layout, dark/blue theme by default, theme switcher (updates instantly)
- No external build step required (Tailwind via CDN for simplicity)

## Quickstart

### 1) Create and activate a venv, install deps

```bash
cd /home/jawand/Documents/omni_chat
python3 -m venv .venv
./.venv/bin/python -m pip install -U pip
./.venv/bin/pip install -r requirements.txt
```

### 2) Configure environment

Copy the example env and edit secrets:

```bash
cp .env.example .env
# Then edit .env to set strong SECRET_KEY and ENCRYPTION_KEY (Fernet 32-byte base64).
```

At minimum, set provider API keys in the app UI under Settings after the server starts.

### 3) Run the app

```bash
./.venv/bin/python run.py
# Visit http://127.0.0.1:5000
```

The database will be created automatically on first run (`omni_chat.db` in project root by default).

## Structure

- `run.py` – entrypoint
- `config.py` – app configuration
- `app/` – Flask package
  - `__init__.py` – app factory, blueprint registration
  - `db.py` – SQLAlchemy init
  - `models.py` – ORM models (ApiKey, ChatSession, Message)
  - `utils/crypto.py` – Fernet-based encryption helpers
  - `providers/` – model provider adapters
    - `base.py`, `openai_provider.py`, `anthropic_provider.py`, `gemini_provider.py`
  - `routes/` – app routes
    - `chat.py`, `settings.py`
  - `templates/` – Jinja templates
    - `base.html`, `chat.html`, `settings.html`
  - `static/` – assets
    - `css/theme.css`, `js/chat.js`

## Notes
- Keys are encrypted at rest using a Fernet key specified by `ENCRYPTION_KEY` in `.env`. Generate with:

```bash
./.venv/bin/python - << 'PY'
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
PY
```

- This demo uses Tailwind via CDN for ease. Theme switching is driven by CSS variables in `static/css/theme.css` and a `<select>` in the header. For production, consider a Tailwind build pipeline and CSP hardening.
- Streaming responses are not implemented in this MVP; requests are synchronous. You can extend providers to enable streaming.

## Troubleshooting
- If provider calls fail, ensure API keys are added in Settings and your model name is valid for that provider.
- If encryption fails, verify `ENCRYPTION_KEY` in `.env` is a valid Fernet key (base64-encoded 32-byte key).
- To reset DB: stop server and remove `omni_chat.db`.
