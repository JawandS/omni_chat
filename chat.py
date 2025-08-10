from dataclasses import dataclass
from typing import List, Dict, Optional
import os
try:
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover - optional dependency in tests
    load_dotenv = None  # type: ignore

# Load .env early so os.getenv picks up OPENAI_API_KEY
if load_dotenv is not None:
    try:
        load_dotenv()
    except Exception:
        pass

# Hardcoded place for the API key (replace with your actual key or use env var)
# Prefer environment variable if present; falls back to the constant placeholder.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "PUT_OPENAI_API_KEY_HERE")

try:
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover - optional dependency in tests
    OpenAI = None  # type: ignore


@dataclass
class ChatReply:
    reply: str

def _format_history_for_openai(history: List[Dict[str, str]], latest_message: str) -> List[Dict[str, str]]:
    """Convert our history list to OpenAI Chat Completions format.

    history: [{"role": "user"|"assistant", "content": str}, ...]
    latest_message: the new user message to append at the end as 'user'.
    """
    msgs: List[Dict[str, str]] = []
    for m in history or []:
        role = m.get("role") or "user"
        content = m.get("content") or ""
        if role not in ("user", "assistant", "system"):
            role = "user"
        msgs.append({"role": role, "content": content})
    # Append current user message
    msgs.append({"role": "user", "content": latest_message})
    return msgs


def _openai_call(model: str, history: List[Dict[str, str]], message: str) -> Optional[str]:
    """Call OpenAI Chat Completions API with formatted history.

    Returns the reply string or None on failure.
    """
    if not OPENAI_API_KEY or OPENAI_API_KEY.startswith("PUT_"):
        return None
    if OpenAI is None:
        return None
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        messages = _format_history_for_openai(history, message)
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.2,
        )
        content = resp.choices[0].message.content if resp.choices else None
        return content or None
    except Exception:
        return None


def generate_reply(provider: str, model: str, message: str, history: Optional[List[Dict[str, str]]] = None) -> ChatReply:
    """Chat generation logic with optional OpenAI backend.

    - If provider == 'openai' and the OpenAI client/key is available, perform a real API call with full history.
    - Otherwise, fall back to echo behavior for reliability in tests/offline.
    """
    if provider.lower() == "openai":
        content = _openai_call(model, history or [], message)
        if content:
            return ChatReply(reply=content)
    # Fallback echo (keeps previous test expectations)
    reply = f"[{provider}/{model}] Echo: {message}"
    return ChatReply(reply=reply)
