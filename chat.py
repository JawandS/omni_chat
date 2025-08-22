"""Chat module for handling AI provider API calls and responses."""

import os
import subprocess
import time
from dataclasses import dataclass
from typing import List, Dict, Optional, Iterator, Any, cast

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

try:
    import requests  # type: ignore
except ImportError:  # pragma: no cover - optional dependency in tests
    requests = None  # type: ignore


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
        provider: Provider name ('openai', 'gemini', or 'ollama').

    Returns:
        API key from environment or empty string if not found.
    """
    key_mapping = {
        "openai": "OPENAI_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "ollama": "",  # Ollama doesn't require API key for local usage
    }
    env_var = key_mapping.get(provider.lower(), "")
    if not env_var:  # Ollama case
        return "local"
    return os.getenv(env_var, "")


def is_ollama_available() -> bool:
    """Check if Ollama is installed and available on the system.

    Returns:
        True if ollama command is available, False otherwise.
    """
    try:
        subprocess.run(
            ["ollama", "--version"], capture_output=True, check=True, timeout=5
        )
        return True
    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ):
        return False


def is_ollama_server_running() -> bool:
    """Check if Ollama server is running.

    Returns:
        True if server is running, False otherwise.
    """
    if requests is None:
        return False

    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=15)
        return response.status_code == 200
    except requests.RequestException:
        return False


def start_ollama_server() -> bool:
    """Start Ollama server if it's not running.

    Returns:
        True if server was started or already running, False on error.
    """
    if is_ollama_server_running():
        return True

    if not is_ollama_available():
        return False

    try:
        # Start ollama serve in background
        subprocess.Popen(
            ["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        # Wait a moment for server to start
        time.sleep(2)
        # Check if it's running now
        return is_ollama_server_running()
    except Exception:
        return False


def get_ollama_models() -> List[str]:
    """Get list of available Ollama models.

    Returns:
        List of model names, empty if Ollama is not available.
    """
    if requests is None or not is_ollama_server_running():
        return []

    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=10)
        if response.status_code == 200:
            data = response.json()
            models = []
            for model in data.get("models", []):
                name = model.get("name", "")  # Keep full name with tag
                if name and name not in models:
                    models.append(name)
            return sorted(models)
    except requests.RequestException:
        pass
    return []


def _format_history_for_openai(
    history: List[Dict[str, str]], latest_message: str
) -> List[Dict[str, str]]:
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


def _openai_call(
    model: str,
    history: List[Dict[str, str]],
    message: str,
    params: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
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
    params = params or {}
    # Whitelist of supported OpenAI Chat Completions parameters
    allowed = {
        "temperature",
        "top_p",
        "max_tokens",
        "presence_penalty",
        "frequency_penalty",
        "seed",
        "stop",
        "response_format",
        "thinking",
        "thinking_budget_tokens",
    }
    call_args = {k: params[k] for k in allowed if k in params}

    if _is_reasoning_model(model):
        # Use Responses API for reasoning models like o3-mini.
        # Casting messages because SDK expects complex union types; runtime accepts our structure.
        # Allow overriding reasoning_effort & temperature for reasoning models
        reasoning_effort = params.get("reasoning_effort", "low")
        reasoning_payload: Dict[str, Any] = {"effort": reasoning_effort}
        reasoning_resp = client.responses.create(  # type: ignore[arg-type,assignment]
            model=model,
            input=cast(Any, messages),
            reasoning=reasoning_payload,
            **({k: v for k, v in call_args.items() if k != "max_tokens"}),
        )
        return getattr(reasoning_resp, "output_text", None)
    else:
        completion_resp = client.chat.completions.create(  # type: ignore[arg-type,assignment]
            model=model,
            messages=cast(Any, messages),
            **call_args,
        )
        # choices attribute is dynamic from SDK; ignore for typing
        content = (
            completion_resp.choices[0].message.content  # type: ignore[attr-defined,index]
            if getattr(completion_resp, "choices", None)
            else None
        )
        return content or None


def _openai_call_stream(
    model: str,
    history: List[Dict[str, str]],
    message: str,
    params: Optional[Dict[str, Any]] = None,
) -> Iterator[str]:
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
    params = params or {}
    allowed = {
        "temperature",
        "top_p",
        "max_tokens",
        "presence_penalty",
        "frequency_penalty",
        "seed",
        "stop",
        "response_format",
        "thinking",
        "thinking_budget_tokens",
    }
    call_args = {k: params[k] for k in allowed if k in params}

    if _is_reasoning_model(model):
        # Reasoning models don't support streaming currently, fall back to non-streaming
        logger.info(
            f"[OPENAI] Using reasoning model {model}, falling back to non-streaming"
        )
        content = _openai_call(model, history, message, params=params)
        if content:
            logger.info(
                f"[OPENAI] Got full content from reasoning model: {len(content)} chars"
            )
            yield content
        return
    else:
        logger.info(f"[OPENAI] Starting streaming for model {model}")
        stream = client.chat.completions.create(  # type: ignore[arg-type]
            model=model,
            messages=cast(Any, messages),
            stream=True,
            **call_args,
        )
        token_count = 0
        for chunk in stream:
            # Guard for union types or unexpected tuple outputs in newer SDKs
            if hasattr(chunk, "choices") and getattr(chunk, "choices"):
                first_choice = getattr(chunk, "choices")[0]
                delta = getattr(first_choice, "delta", None)
                content_piece = getattr(delta, "content", None) if delta else None
                if content_piece:
                    token_count += 1
                    logger.info(f"[OPENAI] Token {token_count}: '{content_piece}'")
                    yield content_piece  # type: ignore[return-value]


def _format_history_for_gemini(
    history: List[Dict[str, str]], latest_message: str
) -> tuple[list[Dict], str]:
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


def _gemini_call(
    model: str,
    history: List[Dict[str, str]],
    message: str,
    params: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
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
    params = params or {}
    allowed = {"temperature", "top_p", "top_k", "max_output_tokens"}
    generation_config = {k: params[k] for k in allowed if k in params}
    # web_search boolean could be toggled via safety_settings or tools in real API; placeholder ignore
    model_obj = genai.GenerativeModel(
        model, generation_config=generation_config or None
    )

    # Start a new chat with prior history and send the latest message
    chat = model_obj.start_chat(history=cast(Any, chat_history))  # type: ignore[arg-type]
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


def _format_history_for_ollama(
    history: List[Dict[str, str]], latest_message: str
) -> List[Dict[str, str]]:
    """Convert history list to Ollama chat format.

    Args:
        history: List of message dictionaries with 'role' and 'content' keys.
        latest_message: The new user message to append at the end.

    Returns:
        Formatted message list for Ollama API.
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


def _ollama_call(
    model: str,
    history: List[Dict[str, str]],
    message: str,
    params: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Call Ollama API with formatted history.

    Args:
        model: The Ollama model name.
        history: Previous message history.
        message: The current user message.
        params: Optional parameters for the model.

    Returns:
        The reply string or None on failure.
    """
    if requests is None or not is_ollama_server_running():
        return None

    messages = _format_history_for_ollama(history, message)
    params = params or {}

    # Map common parameters to Ollama format
    options = {}
    if "temperature" in params:
        options["temperature"] = params["temperature"]
    if "top_p" in params:
        options["top_p"] = params["top_p"]
    if "top_k" in params:
        options["top_k"] = params["top_k"]
    if "max_tokens" in params:
        options["num_predict"] = params["max_tokens"]

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
    }
    if options:
        payload["options"] = options

    try:
        response = requests.post(
            "http://localhost:11434/api/chat", json=payload, timeout=60
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("message", {}).get("content", "")
    except requests.RequestException:
        pass
    return None


def _ollama_call_stream(
    model: str,
    history: List[Dict[str, str]],
    message: str,
    params: Optional[Dict[str, Any]] = None,
) -> Iterator[str]:
    """Call Ollama API with streaming.

    Args:
        model: The Ollama model name.
        history: Previous message history.
        message: The current user message.
        params: Optional parameters for the model.

    Yields:
        Content tokens as they arrive.
    """
    if requests is None or not is_ollama_server_running():
        return

    messages = _format_history_for_ollama(history, message)
    params = params or {}

    # Map common parameters to Ollama format
    options = {}
    if "temperature" in params:
        options["temperature"] = params["temperature"]
    if "top_p" in params:
        options["top_p"] = params["top_p"]
    if "top_k" in params:
        options["top_k"] = params["top_k"]
    if "max_tokens" in params:
        options["num_predict"] = params["max_tokens"]

    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
    }
    if options:
        payload["options"] = options

    try:
        response = requests.post(
            "http://localhost:11434/api/chat", json=payload, stream=True, timeout=60
        )
        if response.status_code == 200:
            for line in response.iter_lines():
                if line:
                    try:
                        data = line.decode("utf-8")
                        import json

                        chunk = json.loads(data)
                        if "message" in chunk and "content" in chunk["message"]:
                            content = chunk["message"]["content"]
                            if content:
                                yield content
                        if chunk.get("done", False):
                            break
                    except json.JSONDecodeError:
                        continue
    except requests.RequestException:
        pass


def _gemini_call_stream(
    model: str,
    history: List[Dict[str, str]],
    message: str,
    params: Optional[Dict[str, Any]] = None,
) -> Iterator[str]:
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
    params = params or {}
    allowed = {"temperature", "top_p", "top_k", "max_output_tokens"}
    generation_config = {k: params[k] for k in allowed if k in params}
    model_obj = genai.GenerativeModel(
        model, generation_config=generation_config or None
    )
    chat = model_obj.start_chat(history=cast(Any, chat_history))  # type: ignore[arg-type]

    # Stream the response
    try:
        response = chat.send_message(user_text, stream=True)
        for chunk in response:
            if hasattr(chunk, "text") and chunk.text:
                yield chunk.text
            elif hasattr(chunk, "candidates") and chunk.candidates:
                for candidate in chunk.candidates:
                    if hasattr(candidate, "content") and candidate.content:
                        if hasattr(candidate.content, "parts"):
                            for part in candidate.content.parts:
                                if hasattr(part, "text") and part.text:
                                    yield part.text
    except StopIteration:
        # Normal end of stream, ignore
        pass
    except Exception:
        # Re-raise other exceptions
        raise


def generate_reply(
    provider: str,
    model: str,
    message: str,
    history: Optional[List[Dict[str, str]]] = None,
    params: Optional[Dict[str, Any]] = None,
) -> ChatReply:
    """Generate a chat response using the specified provider.

    Args:
        provider: AI provider name ('openai', 'gemini', or 'ollama').
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
            content = _openai_call(model, history, message, params=params)
            if content:
                return ChatReply(reply=content)
            # Check for missing key/client
            key = _get_api_key("openai")
            if not key or key.startswith("PUT_") or OpenAI is None:
                return ChatReply(
                    reply="", error="OpenAI API key not set", missing_key_for="openai"
                )
            return ChatReply(reply="", error="OpenAI returned no content")
        except Exception as e:
            return ChatReply(
                reply="", error=f"OpenAI error: {e.__class__.__name__}: {e}"
            )

    elif provider_lower == "gemini":
        try:
            content = _gemini_call(model, history, message, params=params)
            if content:
                return ChatReply(reply=content)
            key = _get_api_key("gemini")
            if not key or key.startswith("PUT_") or genai is None:
                return ChatReply(
                    reply="", error="Gemini API key not set", missing_key_for="gemini"
                )
            return ChatReply(reply="", error="Gemini returned no content")
        except Exception as e:
            return ChatReply(
                reply="", error=f"Gemini error: {e.__class__.__name__}: {e}"
            )

    elif provider_lower == "ollama":
        try:
            if not is_ollama_server_running():
                return ChatReply(
                    reply="",
                    error="Ollama server not running",
                    missing_key_for="ollama",
                )
            content = _ollama_call(model, history, message, params=params)
            if content:
                return ChatReply(reply=content)
            return ChatReply(reply="", error="Ollama returned no content")
        except Exception as e:
            return ChatReply(
                reply="", error=f"Ollama error: {e.__class__.__name__}: {e}"
            )
    else:
        raise ValueError(f"unknown provider: {provider}")


def generate_reply_stream(
    provider: str,
    model: str,
    message: str,
    history: Optional[List[Dict[str, str]]] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Iterator[StreamChunk]:
    """Generate a streaming chat response using the specified provider.

    Args:
        provider: AI provider name ('openai', 'gemini', or 'ollama').
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
                yield StreamChunk(
                    error="OpenAI API key not set", missing_key_for="openai"
                )
                return

            had_content = False
            token_count = 0
            for token in _openai_call_stream(model, history, message, params=params):
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
                yield StreamChunk(
                    error="Gemini API key not set", missing_key_for="gemini"
                )
                return

            had_content = False
            token_count = 0
            for token in _gemini_call_stream(model, history, message, params=params):
                if token:
                    had_content = True
                    token_count += 1
                    logger.info(
                        f"[STREAM] Yielding Gemini token {token_count}: '{token}'"
                    )
                    yield StreamChunk(token=token)

            if not had_content:
                yield StreamChunk(error="Gemini returned no content")

        except Exception as e:
            logger.error(f"[STREAM] Gemini error: {e}")
            yield StreamChunk(error=f"Gemini error: {e.__class__.__name__}: {e}")

    elif provider_lower == "ollama":
        try:
            if not is_ollama_server_running():
                logger.info("[STREAM] Ollama server not running")
                yield StreamChunk(
                    error="Ollama server not running", missing_key_for="ollama"
                )
                return

            had_content = False
            token_count = 0
            for token in _ollama_call_stream(model, history, message, params=params):
                if token:
                    had_content = True
                    token_count += 1
                    logger.info(
                        f"[STREAM] Yielding Ollama token {token_count}: '{token}'"
                    )
                    yield StreamChunk(token=token)

            if not had_content:
                yield StreamChunk(error="Ollama returned no content")

        except Exception as e:
            logger.error(f"[STREAM] Ollama error: {e}")
            yield StreamChunk(error=f"Ollama error: {e.__class__.__name__}: {e}")

    else:
        yield StreamChunk(error=f"unknown provider: {provider}")
