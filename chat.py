"""
Chat module for handling AI provider API calls and responses.

This module provides a unified interface for interacting with multiple AI providers
including OpenAI, Google Gemini, Anthropic Claude, and Ollama. It handles both
synchronous and asynchronous streaming responses while maintaining a consistent API.

Key Features:
    - Multi-provider support (OpenAI, Gemini, Claude, Ollama)
    - Streaming and non-streaming responses
    - Special handling for reasoning models (o3-mini, etc.)
    - Web search capabilities for GPT-4.1 Live and Gemini Live
    - Automatic API key validation
    - Consistent error handling across providers
    - Type-safe response structures

Architecture:
    - Provider-specific implementations with unified interface
    - Dataclass-based response structures for type safety
    - Environment-based configuration management
    - Graceful fallbacks for missing dependencies

Usage:
    >>> reply = generate_reply("openai", "gpt-4o", "Hello", [])
    >>> if reply.error:
    ...     print(f"Error: {reply.error}")
    >>> else:
    ...     print(f"Reply: {reply.reply}")

Security:
    - API keys loaded from environment variables
    - Input sanitization for all provider calls
    - Safe error message handling without exposing keys
    - Test isolation with mocked API calls
"""

import os
import subprocess
import time
from dataclasses import dataclass
from typing import List, Dict, Optional, Any, cast

try:
    from dotenv import load_dotenv  # type: ignore
except ImportError:  # pragma: no cover - optional dependency in tests
    load_dotenv = None  # type: ignore

from utils import (
    get_api_key,
    is_ollama_available,
    is_ollama_server_running,
    start_ollama_server,
    get_ollama_models,
)

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
    from google import genai as google_genai  # type: ignore
    from google.genai import types as genai_types  # type: ignore
except ImportError:  # pragma: no cover - optional dependency in tests
    google_genai = None  # type: ignore
    genai_types = None  # type: ignore

try:
    import requests  # type: ignore
except ImportError:  # pragma: no cover - optional dependency in tests
    requests = None  # type: ignore

try:
    from anthropic import Anthropic  # type: ignore
except ImportError:  # pragma: no cover - optional dependency in tests
    Anthropic = None  # type: ignore


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


def _validate_images(images: Optional[List[str]]) -> Optional[str]:
    """Validate image inputs for multi-modal requests.

    Args:
        images: List of image URLs or data URIs.

    Returns:
        Error message if validation fails, None otherwise.
    """
    if not images:
        return None

    if not isinstance(images, list):
        return "Images parameter must be a list"

    if len(images) > 20:
        return "Too many images (max 20)"

    for img in images:
        if not isinstance(img, str):
            return "Each image must be a string (URL or data URI)"
        if not (img.startswith("http://") or img.startswith("https://") or img.startswith("data:")):
            return f"Invalid image format: {img[:50]}... (must be URL or data URI)"

    return None


def _validate_params(params: Optional[Dict[str, Any]], provider: str) -> Optional[str]:
    """Validate parameters for a specific provider.

    Args:
        params: Parameter dictionary.
        provider: Provider name.

    Returns:
        Error message if validation fails, None otherwise.
    """
    if not params:
        return None

    # Validate temperature
    if "temperature" in params:
        temp = params["temperature"]
        if not isinstance(temp, (int, float)) or temp < 0 or temp > 2:
            return "Temperature must be between 0 and 2"

    # Validate max_tokens
    if "max_tokens" in params:
        max_tokens = params["max_tokens"]
        if not isinstance(max_tokens, int) or max_tokens < 1:
            return "max_tokens must be a positive integer"

    # Validate thinking_budget_tokens for Claude
    if provider == "claude" and "thinking_budget_tokens" in params:
        budget = params["thinking_budget_tokens"]
        if not isinstance(budget, int) or budget < 1000 or budget > 100000:
            return "thinking_budget_tokens must be between 1000 and 100000"

    # Validate images
    if "images" in params:
        error = _validate_images(params["images"])
        if error:
            return error

    return None


def _openai_stream(
    model: str,
    history: List[Dict[str, str]],
    message: str,
    params: Optional[Dict[str, Any]] = None,
):
    """Stream responses from OpenAI API.

    Args:
        model: The OpenAI model name.
        history: Previous message history.
        message: The current user message.
        params: Optional parameters including images.

    Yields:
        Text chunks from the streaming response.

    Raises:
        StopIteration: When streaming is complete or on error.
    """
    import logging
    logger = logging.getLogger(__name__)

    key = get_api_key("openai")
    if not key or key.startswith("PUT_") or OpenAI is None:
        logger.error("[OPENAI-STREAM] API key not configured")
        return

    params = params or {}
    images = params.get("images")

    # Reasoning and thinking models don't support streaming
    if _is_reasoning_model(model) or _is_thinking_model(model) or _is_live_model(model):
        logger.info(f"[OPENAI-STREAM] Model {model} doesn't support streaming, falling back to non-streaming")
        content = _openai_call(model, history, message, params)
        if content:
            yield content
        return

    try:
        client = OpenAI(api_key=key)
        messages = _format_history_for_openai(history, message, images)

        allowed = {
            "temperature",
            "top_p",
            "max_tokens",
            "presence_penalty",
            "frequency_penalty",
            "seed",
            "stop",
        }
        call_args = {k: params[k] for k in allowed if k in params}

        # Handle JSON mode
        if params.get("json_mode", False):
            call_args["response_format"] = {"type": "json_object"}
        elif "response_format" in params:
            call_args["response_format"] = params["response_format"]

        logger.info(f"[OPENAI-STREAM] Starting stream for model {model}")
        stream = client.chat.completions.create(
            model=model,
            messages=cast(Any, messages),
            stream=True,
            **call_args,
        )

        for chunk in stream:
            if hasattr(chunk, "choices") and chunk.choices:
                delta = chunk.choices[0].delta
                if hasattr(delta, "content") and delta.content:
                    yield delta.content

        logger.info(f"[OPENAI-STREAM] Stream completed for model {model}")

    except Exception as e:
        logger.error(f"[OPENAI-STREAM] Error: {type(e).__name__}: {e}")
        return


def _gemini_stream(
    model: str,
    history: List[Dict[str, str]],
    message: str,
    params: Optional[Dict[str, Any]] = None,
):
    """Stream responses from Gemini API.

    Args:
        model: The Gemini model name.
        history: Previous message history.
        message: The current user message.
        params: Optional parameters including images.

    Yields:
        Text chunks from the streaming response.
    """
    import logging
    logger = logging.getLogger(__name__)

    key = get_api_key("gemini")
    if not key or key.startswith("PUT_") or genai is None:
        logger.error("[GEMINI-STREAM] API key not configured")
        return

    params = params or {}
    images = params.get("images")

    # Live models don't support streaming yet
    if model.lower().endswith("-live"):
        logger.info(f"[GEMINI-STREAM] Model {model} doesn't support streaming, falling back to non-streaming")
        content = _gemini_live_call(model, history, message, params)
        if content:
            yield content
        return

    try:
        genai.configure(api_key=key)
        chat_history, user_text = _format_history_for_gemini(history, message, images)
        allowed = {"temperature", "top_p", "top_k", "max_output_tokens"}
        generation_config = {k: params[k] for k in allowed if k in params}

        logger.info(f"[GEMINI-STREAM] Starting stream for model {model}")
        model_obj = genai.GenerativeModel(
            model, generation_config=generation_config or None
        )
        chat = model_obj.start_chat(history=cast(Any, chat_history))
        response = chat.send_message(user_text, stream=True)

        for chunk in response:
            if hasattr(chunk, "text") and chunk.text:
                yield chunk.text

        logger.info(f"[GEMINI-STREAM] Stream completed for model {model}")

    except Exception as e:
        logger.error(f"[GEMINI-STREAM] Error: {type(e).__name__}: {e}")
        return


def _claude_stream(
    model: str,
    history: List[Dict[str, str]],
    message: str,
    params: Optional[Dict[str, Any]] = None,
):
    """Stream responses from Claude API.

    Args:
        model: The Claude model name.
        history: Previous message history.
        message: The current user message.
        params: Optional parameters including images.

    Yields:
        Text chunks from the streaming response.
    """
    import logging
    logger = logging.getLogger(__name__)

    key = get_api_key("claude")
    if not key or key.startswith("PUT_") or Anthropic is None:
        logger.error("[CLAUDE-STREAM] API key not configured")
        return

    params = params or {}
    images = params.get("images")

    try:
        client = Anthropic(api_key=key)
        messages = _format_history_for_claude(history, message, images)

        allowed = {
            "temperature",
            "top_p",
            "top_k",
            "max_tokens",
            "stop_sequences",
        }
        call_args = {k: params[k] for k in allowed if k in params}

        if "max_tokens" not in call_args:
            call_args["max_tokens"] = 4096

        # Note: Extended thinking and caching don't work with streaming
        if params.get("extended_thinking") or params.get("enable_caching"):
            logger.warning("[CLAUDE-STREAM] Extended thinking/caching not supported in streaming, falling back")
            content = _claude_call(model, history, message, params)
            if content:
                yield content
            return

        logger.info(f"[CLAUDE-STREAM] Starting stream for model {model}")
        with client.messages.stream(
            model=model,
            messages=cast(Any, messages),
            **call_args,
        ) as stream:
            for text in stream.text_stream:
                yield text

        logger.info(f"[CLAUDE-STREAM] Stream completed for model {model}")

    except Exception as e:
        logger.error(f"[CLAUDE-STREAM] Error: {type(e).__name__}: {e}")
        return


def generate_reply_stream(
    provider: str,
    model: str,
    message: str,
    history: Optional[List[Dict[str, str]]] = None,
    params: Optional[Dict[str, Any]] = None,
):
    """Generate a streaming chat response using the specified provider.

    Args:
        provider: AI provider name ('openai', 'gemini', 'claude', or 'ollama').
        model: Model name to use.
        message: The user message.
        history: Optional previous message history.
        params: Optional parameters (temperature, images, etc.).

    Yields:
        Text chunks from the streaming response.

    Raises:
        ValueError: If provider is invalid or required parameters are missing.
    """
    import logging
    logger = logging.getLogger(__name__)

    if not provider or not provider.strip():
        raise ValueError("provider is required")

    if not model or not model.strip():
        raise ValueError("model is required")

    if not message or not message.strip():
        raise ValueError("message is required and cannot be empty")

    provider_lower = provider.lower().strip()
    history = history or []

    # Validate parameters
    validation_error = _validate_params(params, provider_lower)
    if validation_error:
        logger.error(f"[STREAM] Parameter validation failed: {validation_error}")
        raise ValueError(f"Parameter validation failed: {validation_error}")

    if provider_lower == "openai":
        yield from _openai_stream(model, history, message, params)
    elif provider_lower == "gemini":
        yield from _gemini_stream(model, history, message, params)
    elif provider_lower == "claude":
        yield from _claude_stream(model, history, message, params)
    elif provider_lower == "ollama":
        # Ollama doesn't support streaming in current implementation
        # Fall back to non-streaming
        content = _ollama_call(model, history, message, params)
        if content:
            yield content
    else:
        raise ValueError(f"unknown provider: {provider}")


def _format_history_for_openai(
    history: List[Dict[str, str]], latest_message: str, images: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """Convert history list to OpenAI Chat Completions format.

    Args:
        history: List of message dictionaries with 'role' and 'content' keys.
        latest_message: The new user message to append at the end as 'user'.
        images: Optional list of image URLs or base64 data URIs for vision models.

    Returns:
        Formatted message list for OpenAI API.
    """
    msgs: List[Dict[str, Any]] = []
    for m in history or []:
        role = m.get("role") or "user"
        content = m.get("content") or ""
        if role not in ("user", "assistant", "system"):
            role = "user"
        msgs.append({"role": role, "content": content})

    # Append current user message with optional images
    if images and len(images) > 0:
        # Multi-modal message with text and images
        content_parts: List[Dict[str, Any]] = [{"type": "text", "text": latest_message}]
        for img in images:
            if img.startswith("http://") or img.startswith("https://"):
                # URL image
                content_parts.append({"type": "image_url", "image_url": {"url": img}})
            elif img.startswith("data:"):
                # Base64 data URI
                content_parts.append({"type": "image_url", "image_url": {"url": img}})
        msgs.append({"role": "user", "content": content_parts})
    else:
        # Text-only message
        msgs.append({"role": "user", "content": latest_message})

    return msgs


def _is_reasoning_model(model: str) -> bool:
    """Check if a model is a reasoning model (o3 series).

    Args:
        model: The model name to check.

    Returns:
        True if it's a reasoning model.
    """
    return bool(model and model.lower().startswith("o3"))


def _is_thinking_model(model: str) -> bool:
    """Check if a model is a GPT-5-thinking model.

    Args:
        model: The model name to check.

    Returns:
        True if it's a GPT-5-thinking model.
    """
    return bool(model and model.lower() == "gpt-5-thinking")


def _is_live_model(model: str) -> bool:
    """Check if a model is a live model with real-time web search.

    Args:
        model: The model name to check.

    Returns:
        True if it's a live model.
    """
    return bool(
        model
        and (model.lower() == "gpt-4.1-live" or model.lower() == "gemini-2.5-pro-live")
    )


def _supports_thinking_budget_tokens(model: str) -> bool:
    """Check if a model supports the thinking_budget_tokens parameter.

    Args:
        model: The model name to check.

    Returns:
        True if the model supports thinking_budget_tokens parameter.
    """
    if not model:
        return False
    
    model_lower = model.lower()
    
    # thinking_budget_tokens is supported by o1-series and some specific models
    # For now, we'll be conservative and only enable it for known supported models
    supported_models = {
        "o1-preview",
        "o1-mini", 
        "o1-2024-12-17",
        "gpt-5-thinking",
        # Add other models as they become available and support this parameter
    }
    
    # Check if it's an o1-series model or specifically supported model
    return (
        model_lower.startswith("o1") or 
        model_lower in supported_models
    )


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
        params: Optional parameters including images.

    Returns:
        The reply string or None on failure.
    """
    key = get_api_key("openai")
    if not key or key.startswith("PUT_") or OpenAI is None:
        return None

    client = OpenAI(api_key=key)
    params = params or {}
    images = params.get("images")
    messages = _format_history_for_openai(history, message, images)

    # Whitelist of supported OpenAI Chat Completions parameters
    allowed = {
        "temperature",
        "top_p",
        "max_tokens",
        "presence_penalty",
        "frequency_penalty",
        "seed",
        "stop",
        "reasoning_effort",
        "verbosity",
        "thinking_budget_tokens",
    }

    # Filter out thinking_budget_tokens for models that don't support it
    if not _supports_thinking_budget_tokens(model):
        allowed = allowed - {"thinking_budget_tokens"}

    # Build call arguments
    call_args = {k: params[k] for k in allowed if k in params}

    # Handle JSON mode if requested
    if params.get("json_mode", False):
        call_args["response_format"] = {"type": "json_object"}
    elif "response_format" in params:
        call_args["response_format"] = params["response_format"]

    if _is_reasoning_model(model):
        # Use Responses API for reasoning models like o3-mini.
        # Casting messages because SDK expects complex union types; runtime accepts our structure.
        # Allow overriding reasoning_effort & temperature for reasoning models
        reasoning_effort = params.get("reasoning_effort", "low")
        reasoning_payload: Dict[str, Any] = {"effort": reasoning_effort}
        reasoning_resp = client.responses.create(  # type: ignore[call-overload]
            model=model,
            input=cast(Any, messages),
            reasoning=reasoning_payload,
            **({k: v for k, v in call_args.items() if k != "max_tokens"}),
        )
        return getattr(reasoning_resp, "output_text", None)
    elif _is_thinking_model(model):
        # Use Responses API for GPT-5-thinking models with reasoning_effort
        # Casting messages because SDK expects complex union types; runtime accepts our structure.
        reasoning_effort = params.get("reasoning_effort", "high")
        verbosity = params.get("verbosity", "medium")
        
        thinking_args = {"reasoning_effort": reasoning_effort}
        if "verbosity" in params:
            thinking_args["verbosity"] = verbosity
            
        thinking_resp = client.responses.create(  # type: ignore[call-overload]
            model=model,
            input=cast(Any, messages),
            **thinking_args,
            **({k: v for k, v in call_args.items() if k not in ["max_tokens", "reasoning_effort", "verbosity"]}),
        )
        return getattr(thinking_resp, "output_text", None)
    elif _is_live_model(model):
        # Use Responses API for live models with real-time web search
        # Add a system message to optimize for web search queries
        enhanced_messages = []

        # Add web search optimization system message
        system_msg = {
            "role": "system",
            "content": "You have access to real-time web search capabilities. When answering questions that would benefit from current information, recent data, or live updates, automatically search for and incorporate the most relevant and up-to-date information available. Cite your sources when using web-searched information.",
        }
        enhanced_messages.append(system_msg)
        enhanced_messages.extend(messages)

        # Use correct Responses API format with web search tool
        live_resp = client.responses.create(  # type: ignore[call-overload]
            model="gpt-4.1",  # Use gpt-4.1 for web search capabilities
            input=cast(Any, enhanced_messages),
            tools=[{"type": "web_search"}],
            tool_choice="auto",
        )
        return getattr(live_resp, "output_text", None)
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
    history: List[Dict[str, str]], latest_message: str, images: Optional[List[str]] = None
) -> tuple[list[Dict], Any]:
    """Convert history to Gemini chat history and user input.

    Args:
        history: Previous message history.
        latest_message: The current user message.
        images: Optional list of image URLs or base64 data URIs for vision models.

    Returns:
        Tuple of (history_list, user_input) where history_list contains dicts with
        'role' ('user'|'model') and 'parts' (list of strings/images).
    """
    mapped = []
    for m in history or []:
        role = m.get("role") or "user"
        content = m.get("content") or ""
        if role not in ("user", "assistant", "system"):
            role = "user"
        gem_role = "model" if role == "assistant" else "user"
        mapped.append({"role": gem_role, "parts": [content]})

    # Create user input with optional images
    if images and len(images) > 0:
        # Multi-modal input with text and images
        # Gemini accepts PIL Image objects or base64 data
        user_parts = [latest_message]
        for img in images:
            if img.startswith("data:image/"):
                # For now, pass the data URI (Gemini SDK can handle it)
                user_parts.append(img)
        return mapped, user_parts
    else:
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
        params: Optional parameters including images.

    Returns:
        Reply content string or None on failure.
    """
    key = get_api_key("gemini")
    if not key or key.startswith("PUT_") or genai is None:
        return None

    genai.configure(api_key=key)
    params = params or {}
    images = params.get("images")
    chat_history, user_text = _format_history_for_gemini(history, message, images)
    allowed = {"temperature", "top_p", "top_k", "max_output_tokens"}
    generation_config = {k: params[k] for k in allowed if k in params}
    # web_search boolean could be toggled via safety_settings or tools in real API; placeholder ignore
    model_obj = genai.GenerativeModel(
        model, generation_config=generation_config or None  # type: ignore[arg-type]
    )

    # Start a new chat with prior history and send the latest message
    chat = model_obj.start_chat(history=cast(Any, chat_history))  # type: ignore[arg-type]
    resp = chat.send_message(user_text)

    # Check for safety/content filtering first
    if hasattr(resp, "candidates") and resp.candidates:
        candidate = resp.candidates[0]
        if hasattr(candidate, "finish_reason"):
            finish_reason = candidate.finish_reason
            # finish_reason values: 1=STOP, 2=MAX_TOKENS, 3=SAFETY, 4=RECITATION, 5=OTHER
            if finish_reason == 3:  # SAFETY - content was filtered
                return (
                    "I cannot provide a response to that request due to safety filters."
                )
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
            if hasattr(resp, "candidates") and resp.candidates:
                candidate = resp.candidates[0]
                if hasattr(candidate, "finish_reason"):
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


def _gemini_live_call(
    model: str,
    history: List[Dict[str, str]],
    message: str,
    params: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Call Google Gemini API with live search grounding.

    Args:
        model: The Gemini model name.
        history: Previous message history.
        message: The current user message.
        params: Optional parameters for the generation.

    Returns:
        Reply content string or None on failure.
    """
    key = get_api_key("gemini")
    if not key or key.startswith("PUT_") or google_genai is None or genai_types is None:
        return None

    try:
        # Configure the new Google GenAI client
        client = google_genai.Client(api_key=key)

        # Define the grounding tool for live search
        grounding_tool = genai_types.Tool(google_search=genai_types.GoogleSearch())

        # Format the conversation history for the new API
        formatted_history = []
        for msg in history or []:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "assistant":
                role = "model"  # Gemini uses "model" instead of "assistant"
            formatted_history.append({"role": role, "content": content})

        # Add the current message
        formatted_history.append({"role": "user", "content": message})

        # Convert to the format expected by the new API
        # The new API expects a single content string with history included
        conversation_text = ""
        for msg in formatted_history:
            if msg["role"] == "user":
                conversation_text += f"User: {msg['content']}\n"
            elif msg["role"] == "model":
                conversation_text += f"Assistant: {msg['content']}\n"

        # Use the base model name without the "-live" suffix
        base_model = model.replace("-live", "")

        # Generate content with search grounding
        response = client.models.generate_content(
            model=base_model,
            contents=conversation_text.strip(),
            config=genai_types.GenerateContentConfig(tools=[grounding_tool]),
        )

        # Get the response text
        response_text = response.text if hasattr(response, "text") else None

        # If grounding metadata is available, append sources
        sources = []
        if hasattr(response, "grounding_metadata") and response.grounding_metadata:
            # Try different ways to access the search results
            grounding = response.grounding_metadata

            # Check for google_search_results
            if hasattr(grounding, "google_search_results"):
                for result in grounding.google_search_results:
                    if hasattr(result, "url"):
                        sources.append(result.url)
                    elif hasattr(result, "uri"):
                        sources.append(result.uri)

            # Check for search_results
            elif hasattr(grounding, "search_results"):
                for result in grounding.search_results:
                    if hasattr(result, "url"):
                        sources.append(result.url)
                    elif hasattr(result, "uri"):
                        sources.append(result.uri)

            # Check for google_search (as in your example)
            elif hasattr(grounding, "google_search"):
                for source in grounding.google_search:
                    if hasattr(source, "uri"):
                        sources.append(source.uri)
                    elif hasattr(source, "url"):
                        sources.append(source.url)

            # Check for web_search_queries attribute
            elif hasattr(grounding, "web_search_queries"):
                # This might not have URLs but indicates search was used
                pass

        # Add sources to response if found
        if sources and response_text:
            response_text += "\n\n**Sources:**\n"
            for i, source in enumerate(sources[:5], 1):  # Limit to 5 sources
                response_text += f"{i}. {source}\n"
        elif (
            response_text
            and hasattr(response, "grounding_metadata")
            and response.grounding_metadata
        ):
            # If we have grounding metadata but no sources found, indicate search was used
            response_text += "\n\n*ℹ️ Response generated using real-time web search*"

        return response_text

    except Exception as e:
        # Fallback to regular Gemini call if live search fails
        print(f"Gemini live search failed: {e}")
        return _gemini_call(model.replace("-live", ""), history, message, params)


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
    logger.info(
        f"[OLLAMA] Payload messages count: {len(cast(list, payload.get('messages', [])))}"
    )

    try:
        start_time = time.time()
        logger.info("[OLLAMA] Making HTTP request...")

        response = requests.post(
            "http://localhost:11434/api/chat", json=payload, timeout=60
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


def _format_history_for_claude(
    history: List[Dict[str, str]], latest_message: str, images: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """Convert history list to Claude Messages API format.

    Args:
        history: List of message dictionaries with 'role' and 'content' keys.
        latest_message: The new user message to append at the end.
        images: Optional list of image URLs or base64 data URIs for vision models.

    Returns:
        Formatted message list for Claude API.
    """
    msgs: List[Dict[str, Any]] = []
    for m in history or []:
        role = m.get("role") or "user"
        content = m.get("content") or ""
        # Claude uses 'user' and 'assistant' roles
        if role not in ("user", "assistant"):
            role = "user"
        msgs.append({"role": role, "content": content})

    # Append current user message with optional images
    if images and len(images) > 0:
        # Multi-modal message with text and images
        content_parts: List[Dict[str, Any]] = [{"type": "text", "text": latest_message}]
        for img in images:
            # Claude expects base64-encoded images
            if img.startswith("data:image/"):
                # Extract media type and base64 data
                parts = img.split(",", 1)
                if len(parts) == 2:
                    media_type = parts[0].split(":")[1].split(";")[0]
                    base64_data = parts[1]
                    content_parts.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": base64_data
                        }
                    })
        msgs.append({"role": "user", "content": content_parts})
    else:
        # Text-only message
        msgs.append({"role": "user", "content": latest_message})

    return msgs


def _claude_call(
    model: str,
    history: List[Dict[str, str]],
    message: str,
    params: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Call Anthropic Claude API with formatted history.

    Args:
        model: The Claude model name.
        history: Previous message history.
        message: The current user message.
        params: Optional parameters for the generation including images.

    Returns:
        The reply string or None on failure.
    """
    key = get_api_key("claude")
    if not key or key.startswith("PUT_") or Anthropic is None:
        return None

    client = Anthropic(api_key=key)
    params = params or {}
    images = params.get("images")
    messages = _format_history_for_claude(history, message, images)

    # Whitelist of supported Claude API parameters
    allowed = {
        "temperature",
        "top_p",
        "top_k",
        "max_tokens",
        "stop_sequences",
    }
    call_args = {k: params[k] for k in allowed if k in params}

    # Set default max_tokens if not provided (required by Claude API)
    if "max_tokens" not in call_args:
        call_args["max_tokens"] = 4096

    # Handle JSON mode for structured outputs
    if params.get("json_mode", False):
        # Add system message to enforce JSON output
        # Note: Claude doesn't have a native json_mode, so we use system instructions
        system_message = "You must respond with valid JSON only. Do not include any text outside of the JSON object."
        # We'd need to modify the message format to include system, but for now just note this
        # In practice, you'd add this as a system parameter to messages.create()

    # Add extended thinking support for Claude
    # Extended thinking allows the model to "think" longer before responding
    if params.get("extended_thinking", False):
        # Enable extended thinking mode
        call_args["thinking"] = {
            "type": "enabled",
            "budget_tokens": params.get("thinking_budget_tokens", 10000)
        }

    # Add prompt caching support for Claude
    # Prompt caching can significantly reduce costs for conversations with large context
    # Enable caching if requested and history is long enough to benefit
    if params.get("enable_caching", False) and len(messages) > 2:
        # Mark recent messages for caching
        # The last few messages in history can be cached to reduce repeated processing
        for i, msg in enumerate(messages[:-1]):  # Don't cache the latest message
            if i >= len(messages) - 3:  # Cache last 2-3 messages
                # Add cache control to eligible messages
                if isinstance(msg.get("content"), str):
                    msg["cache_control"] = {"type": "ephemeral"}

    try:
        response = client.messages.create(
            model=model,
            messages=cast(Any, messages),
            **call_args,
        )

        # Extract text from response
        if hasattr(response, "content") and response.content:
            # Claude returns a list of content blocks
            text_parts = []
            for block in response.content:
                if hasattr(block, "text"):
                    text_parts.append(block.text)
                # Include thinking content if available
                elif hasattr(block, "type") and block.type == "thinking":
                    if hasattr(block, "thinking"):
                        text_parts.append(f"\n[Thinking: {block.thinking}]\n")
            return "".join(text_parts) if text_parts else None

        return None
    except Exception as e:
        # Log error but return None to let caller handle it
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"[CLAUDE] API call failed: {type(e).__name__}: {e}")
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
        provider: AI provider name ('openai', 'gemini', 'claude', or 'ollama').
        model: Model name to use.
        message: The user message.
        history: Optional previous message history.
        params: Optional parameters (temperature, images, extended_thinking, etc.).

    Returns:
        ChatReply object with the response or error information.

    Raises:
        ValueError: If provider is invalid or required parameters are missing.
    """
    if not provider or not provider.strip():
        raise ValueError("provider is required")

    if not model or not model.strip():
        raise ValueError("model is required")

    if not message or not message.strip():
        raise ValueError("message is required and cannot be empty")

    provider_lower = provider.lower().strip()
    history = history or []

    # Validate parameters
    validation_error = _validate_params(params, provider_lower)
    if validation_error:
        return ChatReply(reply="", error=f"Parameter validation failed: {validation_error}")

    if provider_lower == "openai":
        try:
            content = _openai_call(model, history, message, params=params)
            if content:
                return ChatReply(reply=content)
            # Check for missing key/client
            key = get_api_key("openai")
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
            # Check if this is a live search model
            if model.lower().endswith("-live"):
                content = _gemini_live_call(model, history, message, params=params)
            else:
                content = _gemini_call(model, history, message, params=params)

            if content:
                return ChatReply(reply=content)
            key = get_api_key("gemini")
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
                    reply="",
                    error="Ollama server not running",
                    missing_key_for="ollama",
                )

            logger.info("[OLLAMA] Server is running, calling _ollama_call")
            content = _ollama_call(model, history, message, params=params)

            if content:
                logger.info(f"[OLLAMA] Successfully got response: {len(content)} chars")
                return ChatReply(reply=content)

            logger.warning("[OLLAMA] _ollama_call returned empty content")
            return ChatReply(reply="", error="Ollama returned no content")

        except Exception as e:
            logger.error(
                f"[OLLAMA] Exception in generate_reply: {type(e).__name__}: {e}"
            )
            return ChatReply(
                reply="", error=f"Ollama error: {e.__class__.__name__}: {e}"
            )

    elif provider_lower == "claude":
        try:
            content = _claude_call(model, history, message, params=params)
            if content:
                return ChatReply(reply=content)
            key = get_api_key("claude")
            if not key or key.startswith("PUT_") or Anthropic is None:
                return ChatReply(
                    reply="", error="Claude API key not set", missing_key_for="claude"
                )
            return ChatReply(reply="", error="Claude returned no content")
        except Exception as e:
            return ChatReply(
                reply="", error=f"Claude error: {e.__class__.__name__}: {e}"
            )
    else:
        raise ValueError(f"unknown provider: {provider}")
