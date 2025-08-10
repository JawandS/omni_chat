# Omni Chat Flask + Tailwind (Purple)

A minimal Flask app styled with Tailwind (via CDN) using a modern purple gradient.

## Quick start

1. Create and activate a virtual environment (optional but recommended).
2. Install dependencies.
3. Run the app.

### Run locally

```bash
# 1) (optional) create venv
python -m venv .venv
source .venv/bin/activate

# 2) install
pip install -r requirements.txt

# 3) run
python app.py
# then open http://127.0.0.1:5000
```

### Test

```bash
pytest -q
```

### Notes
- Tailwind is loaded via the official CDN for rapid prototyping. For production, consider a build pipeline to tree-shake unused styles.
- Edit templates in `templates/`.
