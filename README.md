# Omni Chat

Minimal Flask chat UI using Tailwind (via CDN). App routes live in `app.py`, with modular helpers:
- `database.py` — SQLite helpers for chats/messages
- `chat.py` — Chat logic (echo fallback + optional OpenAI)

## Quick start

1) Create a virtual env (optional) and install deps
2) Configure OpenAI (optional) via `.env`
3) Run the app

### Setup and run

```bash
# 1) (optional) create venv
python -m venv .venv
source .venv/bin/activate

# 2) install
pip install -r requirements.txt

# 3) (optional) OpenAI key via .env
cat > .env <<'EOF'
OPENAI_API_KEY=sk-...your-key...
EOF

# 4) run
python app.py
# open http://127.0.0.1:5000
```

If no key is configured or provider != `openai`, responses use a safe echo fallback.

## API

- POST `/api/chat`
	- Body: `{ message: str, history?: [{role, content}], provider: str, model: str, chat_id?: int, title?: str }`
	- Reply: `{ reply: str, chat_id: int, title?: str }`

- GET `/api/chats`
	- Reply: `{ chats: [{ id, title, provider, model, updated_at }] }`

- GET `/api/chats/<id>`
	- Reply: `{ chat: {...}, messages: [{ role, content, created_at }] }`

- PATCH `/api/chats/<id>`
	- Body: `{ title?: str, provider?: str, model?: str }`
	- Reply: `{ ok: true }`

- DELETE `/api/chats/<id>`
	- Reply: `{ ok: true }`

## Development

### Run tests

```bash
pytest -q
```

### Notes
- Tailwind loads via CDN for speed. For production, consider a build pipeline to tree-shake styles.
- SQLite DB is created under `instance/omni_chat.db`.
- The UI centers the chat title and includes New/Delete chat buttons. Delete will switch to the next chat if one exists, or start a new chat.
