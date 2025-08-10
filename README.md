# Omni Chat

A simple and lightweight chat interface with a model selector you control (uses API calls). Lets you switch models / providers mid chat. Meant to run locally, uses SQLite to store history. 

## Quick start

Prereqs: Python 3.10+

```bash
# 1) (optional) create a virtual environment
python -m venv .venv
source .venv/bin/activate

# 2) install dependencies
pip install -r requirements.txt

# 3) run the app
python app.py
# open http://127.0.0.1:5000

# 4) configure API key (settings icon or .env file)
OPENAI_API_KEY=sk-...your-openai-key...
GEMINI_API_KEY=...your-gemini-key...
```

## Provider and model support
- Currently supporting OpenAI/Gemini
- You can update `static/providers.json` for other models (might need to customize) `chat.py` for a different API call

# Dev
## Structure
- `app.py`: main file with routes
- `chat.py`: call various APIs
- `database.py`: integrate with SQLite

## Run tests

```bash
pytest -q
```

Notes:
- Tests use a temp SQLite DB and monkeypatch provider calls – no real network calls.
- The main DB lives at `instance/omni_chat.db` (created on first run).

## Troubleshooting

- Missing API key: The message shows an inline error and may auto‑open Settings. Add your key and retry.
- OpenAI reasoning models (o3*): Make sure your account has access; if calls fail, try a standard model to validate setup.
- Reset the database: Stop the app and delete `instance/omni_chat.db` (you’ll lose chats).

## License

MIT License. See `LICENSE.md` if present; otherwise the project is intended to be used under the MIT terms.

## Contributing

Contributions are welcome! Feel free to open issues or pull requests for bugs, features, or docs. Please run the test suite (`pytest -q`) before submitting and update as needed.
