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

# Hardcoded placeholders; actual values are read from environment at call time.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "PUT_OPENAI_API_KEY_HERE")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "PUT_GEMINI_API_KEY_HERE")

def _get_openai_key() -> str:
    return os.getenv("OPENAI_API_KEY", "")

def _get_gemini_key() -> str:
    return os.getenv("GEMINI_API_KEY", "")

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
    warning: Optional[str] = None
    error: Optional[str] = None
    missing_key_for: Optional[str] = None

@dataclass
class StreamChunk:
    token: Optional[str] = None
    warning: Optional[str] = None
    error: Optional[str] = None
    missing_key_for: Optional[str] = None

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


def _openai_is_reasoning_model(model: str) -> bool:
    m = (model or "").lower()
    # Treat o3 family as reasoning models using the Responses API
    return m.startswith("o3")


def _openai_call(model: str, history: List[Dict[str, str]], message: str) -> Optional[str]:
    """Call OpenAI Chat Completions API with formatted history.

    Returns the reply string or None on failure.
    """
    key = _get_openai_key()
    if not key or key.startswith("PUT_"):
        return None
    if OpenAI is None:
        return None
    client = OpenAI(api_key=key)
    messages = _format_history_for_openai(history, message)
    if _openai_is_reasoning_model(model):
        # Use Responses API for reasoning models like o3-mini
        resp = client.responses.create(
            model=model,
            input=messages,
            reasoning={"effort": "low"},
        )
        # The Responses API returns output_text
        content = getattr(resp, "output_text", None)
        return content or None
    else:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
        )
        content = resp.choices[0].message.content if resp.choices else None
        return content or None


def _openai_call_stream(model: str, history: List[Dict[str, str]], message: str):
    """Call OpenAI Chat Completions API with streaming.
    
    Yields content tokens as they arrive, or None on failure.
    """
    key = _get_openai_key()
    if not key or key.startswith("PUT_"):
        return
    if OpenAI is None:
        return
    
    client = OpenAI(api_key=key)
    messages = _format_history_for_openai(history, message)
    
    if _openai_is_reasoning_model(model):
        # Reasoning models don't support streaming currently, fall back to non-streaming
        content = _openai_call(model, history, message)
        if content:
            yield content
        return
    else:
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
        )
        for chunk in stream:
            if chunk.choices:
                delta = chunk.choices[0].delta
                if hasattr(delta, 'content') and delta.content:
                    yield delta.content


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
    key = _get_gemini_key()
    if not key or key.startswith("PUT_"):
        return None
    if genai is None:
        return None
    genai.configure(api_key=key)
    chat_history, user_text = _format_history_for_gemini(history, message)
    # Gemini 2.5 and others are handled by the same client
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


def _gemini_call_stream(model: str, history: List[Dict[str, str]], message: str):
    """Call Google Gemini API with streaming.
    
    Yields content tokens as they arrive, or None on failure.
    """
    key = _get_gemini_key()
    if not key or key.startswith("PUT_"):
        return
    if genai is None:
        return
    
    genai.configure(api_key=key)
    chat_history, user_text = _format_history_for_gemini(history, message)
    model_obj = genai.GenerativeModel(model)
    chat = model_obj.start_chat(history=chat_history)
    
    # Stream the response
    response = chat.send_message(user_text, stream=True)
    for chunk in response:
        if hasattr(chunk, 'text') and chunk.text:
            yield chunk.text
        elif hasattr(chunk, 'candidates') and chunk.candidates:
            for candidate in chunk.candidates:
                if hasattr(candidate, 'content') and candidate.content:
                    if hasattr(candidate.content, 'parts'):
                        for part in candidate.content.parts:
                            if hasattr(part, 'text') and part.text:
                                yield part.text


def generate_reply(provider: str, model: str, message: str, history: Optional[List[Dict[str, str]]] = None) -> ChatReply:
    """Chat generation logic with optional OpenAI backend.

    - If provider == 'openai' and the OpenAI client/key is available, perform a real API call with full history.
    - Otherwise, fall back to echo behavior for reliability in tests/offline.
    """
    plow = provider.lower()
    hist = history or []
    if plow == "openai":
        try:
            content = _openai_call(model, hist, message)
            if content:
                return ChatReply(reply=content)
            # If no content, check for missing key/client
            k = _get_openai_key()
            missing = (not k or k.startswith("PUT_") or OpenAI is None)
            if missing:
                return ChatReply(reply="", error="OpenAI API key not set", missing_key_for="openai")
            return ChatReply(reply="", error="OpenAI returned no content")
        except Exception as e:
            # Provide a detailed error for developers
            return ChatReply(reply="", error=f"OpenAI error: {e.__class__.__name__}: {e}")
    elif plow == "gemini":
        try:
            content = _gemini_call(model, hist, message)
            if content:
                return ChatReply(reply=content)
            k = _get_gemini_key()
            missing = (not k or k.startswith("PUT_") or genai is None)
            if missing:
                return ChatReply(reply="", error="Gemini API key not set", missing_key_for="gemini")
            return ChatReply(reply="", error="Gemini returned no content")
        except Exception as e:
            return ChatReply(reply="", error=f"Gemini error: {e.__class__.__name__}: {e}")
    elif plow in ("", None):  # type: ignore[comparison-overlap]
        raise ValueError("provider is required")
    else:
        # Unrecognized provider -> signal error upstream
        raise ValueError(f"unknown provider: {provider}")


def generate_reply_stream(provider: str, model: str, message: str, history: Optional[List[Dict[str, str]]] = None):
    """Streaming chat generation logic.
    
    Yields StreamChunk objects with tokens, errors, or warnings.
    """
    plow = provider.lower()
    hist = history or []
    
    if plow == "openai":
        try:
            k = _get_openai_key()
            missing = (not k or k.startswith("PUT_") or OpenAI is None)
            if missing:
                yield StreamChunk(error="OpenAI API key not set", missing_key_for="openai")
                return
            
            had_content = False
            for token in _openai_call_stream(model, hist, message):
                if token:
                    had_content = True
                    yield StreamChunk(token=token)
            
            if not had_content:
                yield StreamChunk(error="OpenAI returned no content")
                
        except Exception as e:
            yield StreamChunk(error=f"OpenAI error: {e.__class__.__name__}: {e}")
    
    elif plow == "gemini":
        try:
            k = _get_gemini_key()
            missing = (not k or k.startswith("PUT_") or genai is None)
            if missing:
                yield StreamChunk(error="Gemini API key not set", missing_key_for="gemini")
                return
            
            had_content = False
            for token in _gemini_call_stream(model, hist, message):
                if token:
                    had_content = True
                    yield StreamChunk(token=token)
            
            if not had_content:
                yield StreamChunk(error="Gemini returned no content")
                
        except Exception as e:
            yield StreamChunk(error=f"Gemini error: {e.__class__.__name__}: {e}")
    
    elif plow in ("", None):  # type: ignore[comparison-overlap]
        yield StreamChunk(error="provider is required")
    else:
        yield StreamChunk(error=f"unknown provider: {provider}")
