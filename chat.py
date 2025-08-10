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

# Hardcoded place for the API keys (replace with your actual keys or use env vars)
# Prefer environment variables if present; fall back to constant placeholders.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "PUT_OPENAI_API_KEY_HERE")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "PUT_GEMINI_API_KEY_HERE")

try:
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover - optional dependency in tests
    OpenAI = None  # type: ignore

try:
    import google.generativeai as genai  # type: ignore
except Exception:  # pragma: no cover - optional dependency in tests
    genai = None  # type: ignore


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


def _format_history_for_gemini(history: List[Dict[str, str]], latest_message: str):
    """Convert history to Gemini chat history and user input.

    Returns (history_list, user_text) where history_list is a list of dicts with
    'role' ('user'|'model') and 'parts' (list of strings), and user_text is the
    current user message to send.
    """
    mapped = []
    for m in history or []:
        role = m.get("role") or "user"
        content = m.get("content") or ""
        if role not in ("user", "assistant", "system"):
            role = "user"
        gem_role = "model" if role == "assistant" else "user"
        mapped.append({"role": gem_role, "parts": [content]})
    return mapped, latest_message


def _gemini_call(model: str, history: List[Dict[str, str]], message: str) -> Optional[str]:
    """Call Google Gemini with formatted history.

    Returns reply content string or None on failure.
    """
    if not GEMINI_API_KEY or GEMINI_API_KEY.startswith("PUT_"):
        return None
    if genai is None:
        return None
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        chat_history, user_text = _format_history_for_gemini(history, message)
        model_obj = genai.GenerativeModel(model)
        # Start a new chat with prior history and send the latest message
        chat = model_obj.start_chat(history=chat_history)
        resp = chat.send_message(user_text)
        # Get text output (first candidate)
        if hasattr(resp, "text") and resp.text:
            return str(resp.text)
        # Fallback: try candidates list
        if getattr(resp, "candidates", None):
            for cand in resp.candidates:
                parts = getattr(getattr(cand, "content", None), "parts", None)
                if parts:
                    return str(parts[0].text)
        return None
    except Exception:
        return None


def generate_reply(provider: str, model: str, message: str, history: Optional[List[Dict[str, str]]] = None) -> ChatReply:
    """Chat generation logic with optional OpenAI backend.

    - If provider == 'openai' and the OpenAI client/key is available, perform a real API call with full history.
    - Otherwise, fall back to echo behavior for reliability in tests/offline.
    """
    plow = provider.lower()
    hist = history or []
    if plow == "openai":
        content = _openai_call(model, hist, message)
        if content:
            return ChatReply(reply=content)
    elif plow == "gemini":
        content = _gemini_call(model, hist, message)
        if content:
            return ChatReply(reply=content)
    elif plow in ("", None):  # type: ignore[comparison-overlap]
        raise ValueError("provider is required")
    else:
        # Unrecognized provider -> signal error upstream
        raise ValueError(f"unknown provider: {provider}")
    # Fallback when provider is recognized but API path returned no content
    reply = f"[{provider}/{model}]: {message}"
    return ChatReply(reply=reply)
