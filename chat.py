"""Chat module for handling AI provider API calls and responses."""

import os
from dataclasses import dataclass
from typing import List, Dict, Optional, Iterator

try:
    from dotenv import load_dotenv  # type: ignore
except ImportError:  # pragma: no cover - optional dependency in tests
    load_dotenv = None  # type: ignore

# Load .env early so os.getenv picks up API keys
if load_dotenv is not None:
    try:
        load_dotenv()
    except Exception:
        pass

try:
    from openai import OpenAI  # type: ignore
except ImportError:  # pragma: no cover - optional dependency in tests
    OpenAI = None  # type: ignore

try:
    import google.generativeai as genai  # type: ignore
except ImportError:  # pragma: no cover - optional dependency in tests
    genai = None  # type: ignore


@dataclass
class ChatReply:
    """Response from a chat generation call.
    
    Attributes:
        reply: The generated response text.
        warning: Optional warning message.
        error: Optional error message.
        missing_key_for: Optional provider name if API key is missing.
    """
    reply: str
    warning: Optional[str] = None
    error: Optional[str] = None
    missing_key_for: Optional[str] = None


@dataclass
class StreamChunk:
    """A chunk of streamed response.
    
    Attributes:
        token: Optional text token from the stream.
        warning: Optional warning message.
        error: Optional error message.
        missing_key_for: Optional provider name if API key is missing.
    """
    token: Optional[str] = None
    warning: Optional[str] = None
    error: Optional[str] = None
    missing_key_for: Optional[str] = None


def _get_api_key(provider: str) -> str:
    """Get API key for the specified provider.
    
    Args:
        provider: Provider name ('openai' or 'gemini').
        
    Returns:
        API key from environment or empty string if not found.
    """
    key_mapping = {
        "openai": "OPENAI_API_KEY",
        "gemini": "GEMINI_API_KEY",
    }
    env_var = key_mapping.get(provider.lower(), "")
    return os.getenv(env_var, "")

def _format_history_for_openai(history: List[Dict[str, str]], latest_message: str) -> List[Dict[str, str]]:
    """Convert history list to OpenAI Chat Completions format.

    Args:
        history: List of message dictionaries with 'role' and 'content' keys.
        latest_message: The new user message to append at the end as 'user'.
        
    Returns:
        Formatted message list for OpenAI API.
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


def _is_reasoning_model(model: str) -> bool:
    """Check if the model is a reasoning model (o3 family) that uses Responses API.
    
    Args:
        model: The model name to check.
        
    Returns:
        True if the model is a reasoning model.
    """
    return (model or "").lower().startswith("o3")


def _openai_call(model: str, history: List[Dict[str, str]], message: str) -> Optional[str]:
    """Call OpenAI API with formatted history.

    Args:
        model: The OpenAI model name.
        history: Previous message history.
        message: The current user message.
        
    Returns:
        The reply string or None on failure.
    """
    key = _get_api_key("openai")
    if not key or key.startswith("PUT_") or OpenAI is None:
        return None
        
    client = OpenAI(api_key=key)
    messages = _format_history_for_openai(history, message)
    
    if _is_reasoning_model(model):
        # Use Responses API for reasoning models like o3-mini
        resp = client.responses.create(
            model=model,
            input=messages,
            reasoning={"effort": "low"},
        )
        return getattr(resp, "output_text", None)
    else:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
        )
        content = resp.choices[0].message.content if resp.choices else None
        return content or None


def _openai_call_stream(model: str, history: List[Dict[str, str]], message: str) -> Iterator[str]:
    """Call OpenAI API with streaming.
    
    Args:
        model: The OpenAI model name.
        history: Previous message history.
        message: The current user message.
        
    Yields:
        Content tokens as they arrive.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    key = _get_api_key("openai")
    if not key or key.startswith("PUT_") or OpenAI is None:
        return
    
    client = OpenAI(api_key=key)
    messages = _format_history_for_openai(history, message)
    
    if _is_reasoning_model(model):
        # Reasoning models don't support streaming currently, fall back to non-streaming
        logger.info(f"[OPENAI] Using reasoning model {model}, falling back to non-streaming")
        content = _openai_call(model, history, message)
        if content:
            logger.info(f"[OPENAI] Got full content from reasoning model: {len(content)} chars")
            yield content
        return
    else:
        logger.info(f"[OPENAI] Starting streaming for model {model}")
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
        )
        token_count = 0
        for chunk in stream:
            if chunk.choices:
                delta = chunk.choices[0].delta
                if hasattr(delta, 'content') and delta.content:
                    token_count += 1
                    logger.info(f"[OPENAI] Token {token_count}: '{delta.content}'")
                    yield delta.content


def _format_history_for_gemini(history: List[Dict[str, str]], latest_message: str) -> tuple[list[Dict], str]:
    """Convert history to Gemini chat history and user input.

    Args:
        history: Previous message history.
        latest_message: The current user message.
        
    Returns:
        Tuple of (history_list, user_text) where history_list contains dicts with
        'role' ('user'|'model') and 'parts' (list of strings).
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
    """Call Google Gemini API with formatted history.

    Args:
        model: The Gemini model name.
        history: Previous message history.
        message: The current user message.
        
    Returns:
        Reply content string or None on failure.
    """
    key = _get_api_key("gemini")
    if not key or key.startswith("PUT_") or genai is None:
        return None
        
    genai.configure(api_key=key)
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


def _gemini_call_stream(model: str, history: List[Dict[str, str]], message: str) -> Iterator[str]:
    """Call Google Gemini API with streaming.
    
    Args:
        model: The Gemini model name.
        history: Previous message history.
        message: The current user message.
        
    Yields:
        Content tokens as they arrive.
    """
    key = _get_api_key("gemini")
    if not key or key.startswith("PUT_") or genai is None:
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
    """Generate a chat response using the specified provider.

    Args:
        provider: AI provider name ('openai' or 'gemini').
        model: Model name to use.
        message: The user message.
        history: Optional previous message history.
        
    Returns:
        ChatReply object with the response or error information.
        
    Raises:
        ValueError: If provider is invalid or required parameters are missing.
    """
    if not provider or not provider.strip():
        raise ValueError("provider is required")
    
    if not model or not model.strip():
        raise ValueError("model is required")
    
    provider_lower = provider.lower().strip()
    history = history or []
    
    if provider_lower == "openai":
        try:
            content = _openai_call(model, history, message)
            if content:
                return ChatReply(reply=content)
            # Check for missing key/client
            key = _get_api_key("openai")
            if not key or key.startswith("PUT_") or OpenAI is None:
                return ChatReply(reply="", error="OpenAI API key not set", missing_key_for="openai")
            return ChatReply(reply="", error="OpenAI returned no content")
        except Exception as e:
            return ChatReply(reply="", error=f"OpenAI error: {e.__class__.__name__}: {e}")
            
    elif provider_lower == "gemini":
        try:
            content = _gemini_call(model, history, message)
            if content:
                return ChatReply(reply=content)
            key = _get_api_key("gemini")
            if not key or key.startswith("PUT_") or genai is None:
                return ChatReply(reply="", error="Gemini API key not set", missing_key_for="gemini")
            return ChatReply(reply="", error="Gemini returned no content")
        except Exception as e:
            return ChatReply(reply="", error=f"Gemini error: {e.__class__.__name__}: {e}")
    else:
        raise ValueError(f"unknown provider: {provider}")


def generate_reply_stream(provider: str, model: str, message: str, history: Optional[List[Dict[str, str]]] = None) -> Iterator[StreamChunk]:
    """Generate a streaming chat response using the specified provider.
    
    Args:
        provider: AI provider name ('openai' or 'gemini').
        model: Model name to use.
        message: The user message.
        history: Optional previous message history.
        
    Yields:
        StreamChunk objects with tokens, errors, or warnings.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    if not provider or not provider.strip():
        yield StreamChunk(error="provider is required")
        return
        
    if not model or not model.strip():
        yield StreamChunk(error="model is required")
        return
    
    provider_lower = provider.lower().strip()
    history = history or []
    
    logger.info(f"[STREAM] Starting stream for provider: {provider}, model: {model}")
    
    if provider_lower == "openai":
        try:
            key = _get_api_key("openai")
            if not key or key.startswith("PUT_") or OpenAI is None:
                logger.info("[STREAM] OpenAI API key missing")
                yield StreamChunk(error="OpenAI API key not set", missing_key_for="openai")
                return
            
            had_content = False
            token_count = 0
            for token in _openai_call_stream(model, history, message):
                if token:
                    had_content = True
                    token_count += 1
                    logger.info(f"[STREAM] Yielding token {token_count}: '{token}'")
                    yield StreamChunk(token=token)
            
            if not had_content:
                logger.info("[STREAM] No content received from OpenAI")
                yield StreamChunk(error="OpenAI returned no content")
                
        except Exception as e:
            logger.error(f"[STREAM] OpenAI error: {e}")
            yield StreamChunk(error=f"OpenAI error: {e.__class__.__name__}: {e}")
    
    elif provider_lower == "gemini":
        try:
            key = _get_api_key("gemini")
            if not key or key.startswith("PUT_") or genai is None:
                yield StreamChunk(error="Gemini API key not set", missing_key_for="gemini")
                return
            
            had_content = False
            token_count = 0
            for token in _gemini_call_stream(model, history, message):
                if token:
                    had_content = True
                    token_count += 1
                    logger.info(f"[STREAM] Yielding Gemini token {token_count}: '{token}'")
                    yield StreamChunk(token=token)
            
            if not had_content:
                yield StreamChunk(error="Gemini returned no content")
                
        except Exception as e:
            logger.error(f"[STREAM] Gemini error: {e}")
            yield StreamChunk(error=f"Gemini error: {e.__class__.__name__}: {e}")
    
    else:
        yield StreamChunk(error=f"unknown provider: {provider}")


# Legacy functions for backward compatibility with tests
def _get_openai_key() -> str:
    """Legacy function for backward compatibility."""
    return _get_api_key("openai")


def _get_gemini_key() -> str:
    """Legacy function for backward compatibility."""
    return _get_api_key("gemini")
