"""Chat module for handling AI provider API calls and responses."""

import os
import subprocess
import time
from dataclasses import dataclass
from typing import List, Dict, Optional, Any, cast

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
        subprocess.run(["ollama", "--version"], capture_output=True, check=True, timeout=5)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


def is_ollama_server_running() -> bool:
    """Check if Ollama server is running.
    
    Returns:
        True if server is running, False otherwise.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    if requests is None:
        logger.warning("[OLLAMA] requests library not available for server check")
        return False
        
    try:
        logger.info("[OLLAMA] Checking if server is running at http://localhost:11434/api/tags")
        response = requests.get("http://localhost:11434/api/tags", timeout=15)
        
        if response.status_code == 200:
            logger.info("[OLLAMA] Server is running and responding")
            return True
        else:
            logger.warning(f"[OLLAMA] Server responded with status {response.status_code}")
            return False
            
    except requests.RequestException as e:
        logger.warning(f"[OLLAMA] Server check failed: {type(e).__name__}: {e}")
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
        subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
    model_obj = genai.GenerativeModel(model, generation_config=generation_config or None)

    # Start a new chat with prior history and send the latest message
    chat = model_obj.start_chat(history=cast(Any, chat_history))  # type: ignore[arg-type]
    resp = chat.send_message(user_text)

    # Check for safety/content filtering first
    if hasattr(resp, 'candidates') and resp.candidates:
        candidate = resp.candidates[0]
        if hasattr(candidate, 'finish_reason'):
            finish_reason = candidate.finish_reason
            # finish_reason values: 1=STOP, 2=MAX_TOKENS, 3=SAFETY, 4=RECITATION, 5=OTHER
            if finish_reason == 3:  # SAFETY - content was filtered
                return "I cannot provide a response to that request due to safety filters."
            elif finish_reason == 4:  # RECITATION - content contained citations
                return "I cannot provide a response that might contain recitations or copyrighted content."
            elif finish_reason == 2:  # MAX_TOKENS - response was truncated
                # Try to get partial content if available
                pass
            elif finish_reason not in (1, 2):  # Not STOP or MAX_TOKENS
                return "I cannot provide a response to that request."

    # Get text output (first candidate)
    try:
        if hasattr(resp, "text") and resp.text:
            return str(resp.text)
    except ValueError as e:
        # Handle the case where response.text fails due to no valid parts
        if "response.text" in str(e) and "finish_reason" in str(e):
            # Try to extract finish_reason from candidates
            if hasattr(resp, 'candidates') and resp.candidates:
                candidate = resp.candidates[0]
                if hasattr(candidate, 'finish_reason'):
                    finish_reason = candidate.finish_reason
                    if finish_reason == 3:
                        return "I cannot provide a response to that request due to safety filters."
                    elif finish_reason == 4:
                        return "I cannot provide a response that might contain recitations or copyrighted content."
                    else:
                        return "I cannot generate a response to that request."
            return "I cannot generate a response to that request."
        raise  # Re-raise if it's a different ValueError
    
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
    import logging
    
    logger = logging.getLogger(__name__)
    
    if requests is None:
        logger.error("[OLLAMA] requests library not available")
        return None
        
    if not is_ollama_server_running():
        logger.error("[OLLAMA] Ollama server is not running")
        return None

    logger.info(f"[OLLAMA] Starting request to model: {model}")
    logger.info(f"[OLLAMA] Message length: {len(message)} chars")
    logger.info(f"[OLLAMA] History length: {len(history or [])} messages")

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
        logger.info(f"[OLLAMA] Using options: {options}")

    logger.info(f"[OLLAMA] Sending request to http://localhost:11434/api/chat")
    logger.info(f"[OLLAMA] Payload model: {payload['model']}")
    logger.info(f"[OLLAMA] Payload messages count: {len(payload['messages'])}")

    try:
        start_time = time.time()
        logger.info("[OLLAMA] Making HTTP request...")
        
        response = requests.post(
            "http://localhost:11434/api/chat",
            json=payload,
            timeout=60
        )
        
        elapsed_time = time.time() - start_time
        logger.info(f"[OLLAMA] Request completed in {elapsed_time:.2f}s")
        logger.info(f"[OLLAMA] Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"[OLLAMA] Response data keys: {list(data.keys())}")
            
            message_content = data.get("message", {}).get("content", "")
            logger.info(f"[OLLAMA] Response length: {len(message_content)} chars")
            
            if message_content:
                logger.info(f"[OLLAMA] Response preview: {message_content[:100]}...")
                return message_content
            else:
                logger.warning("[OLLAMA] Empty response content")
                return ""
        else:
            logger.error(f"[OLLAMA] HTTP error {response.status_code}: {response.text}")
            
    except requests.RequestException as e:
        logger.error(f"[OLLAMA] Request exception: {type(e).__name__}: {e}")
    except Exception as e:
        logger.error(f"[OLLAMA] Unexpected error: {type(e).__name__}: {e}")
        
    logger.error("[OLLAMA] Request failed, returning None")
    return None


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
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            logger.info(f"[OLLAMA] generate_reply called for model: {model}")
            
            if not is_ollama_server_running():
                logger.warning("[OLLAMA] Server not running")
                return ChatReply(
                    reply="", error="Ollama server not running", missing_key_for="ollama"
                )
                
            logger.info("[OLLAMA] Server is running, calling _ollama_call")
            content = _ollama_call(model, history, message, params=params)
            
            if content:
                logger.info(f"[OLLAMA] Successfully got response: {len(content)} chars")
                return ChatReply(reply=content)
                
            logger.warning("[OLLAMA] _ollama_call returned empty content")
            return ChatReply(reply="", error="Ollama returned no content")
            
        except Exception as e:
            logger.error(f"[OLLAMA] Exception in generate_reply: {type(e).__name__}: {e}")
            return ChatReply(
                reply="", error=f"Ollama error: {e.__class__.__name__}: {e}"
            )
    else:
        raise ValueError(f"unknown provider: {provider}")
