"""Main Flask application for the Omni Chat application."""

import json
import logging
import os
from datetime import datetime, UTC
from typing import Optional, Generator

from dotenv import load_dotenv, set_key, unset_key, dotenv_values
from flask import Flask, render_template, request, jsonify, Response

from database import (
    init_app as db_init_app,
    init_db,
    commit,
    create_chat,
    update_chat_meta,
    insert_message,
    touch_chat,
    list_chats,
    get_chat as db_get_chat,
    get_messages,
    update_chat as db_update_chat,
    delete_chat,
)
from chat import generate_reply, generate_reply_stream, is_ollama_available, start_ollama_server, get_ollama_models


def _validate_chat_request(data: dict) -> tuple[str, str, str]:
    """Validate and extract required chat parameters.

    Args:
        data: Request JSON data.

    Returns:
        Tuple of (message, provider, model).

    Raises:
        ValueError: If required parameters are missing or invalid.
    """
    message = (data.get("message") or "").strip()
    if not message:
        raise ValueError("message is required")

    provider = (data.get("provider") or "").strip()
    if not provider:
        raise ValueError("provider is required")

    model = (data.get("model") or "").strip()
    if not model:
        raise ValueError("model is required")

    return message, provider, model


def _create_or_update_chat(
    chat_id: Optional[int], title: str, provider: str, model: str, now: str
) -> int:
    """Create a new chat or update existing chat metadata.

    Args:
        chat_id: Optional existing chat ID.
        title: Chat title.
        provider: AI provider name.
        model: AI model name.
        now: Current timestamp.

    Returns:
        Chat ID (new or existing).
    """
    if not chat_id:
        chat_id = create_chat(title, provider, model, now)
        logging.getLogger(__name__).info(f"Created new chat with ID: {chat_id}")
    else:
        update_chat_meta(chat_id, provider, model, now)
    return chat_id


def create_app() -> Flask:
    """Application factory to create and configure the Flask app.

    Returns:
        Configured Flask application instance.
    """
    app = Flask(__name__)

    # Set up logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Safety check: warn if running in apparent test mode without proper test setup
    if app.config.get("TESTING") and not os.environ.get("PYTEST_CURRENT_TEST"):
        logger.warning(
            "App configured for testing but not running under pytest - this may affect production resources!"
        )

    # Configure DB integration (path, teardown)
    db_init_app(app)

    with app.app_context():
        init_db()

    # Default path to .env can be overridden in tests via app.config['ENV_PATH']
    app.config.setdefault("ENV_PATH", os.path.join(app.root_path, ".env"))

    @app.route("/")
    def home():
        """Render the main chat interface."""
        return render_template("index.html")

    @app.post("/api/chat")
    def api_chat():
        """Non-streaming chat endpoint that stores messages and generates a reply.

        Expected JSON body:
            {
                "message": str,
                "chat_id": int (optional),
                "provider": str,
                "model": str,
                "title": str (optional)
            }

        Returns:
            JSON response with reply, chat_id, and optional error/warning information.
        """
        try:
            data = request.get_json(silent=True) or {}
            message, provider, model = _validate_chat_request(data)

            logger.info(f"[NON-STREAMING] Received message: {message[:50]}...")
            logger.info(f"[NON-STREAMING] Provider: {provider}, Model: {model}")

            chat_id = data.get("chat_id")
            title = (data.get("title") or "").strip()
            now = datetime.now(UTC).isoformat()

            # Generate default title if needed
            if not chat_id and not title:
                title = (
                    (message[:48] + "…") if len(message) > 49 else message or "New chat"
                )

            # Create or update chat
            chat_id = _create_or_update_chat(chat_id, title, provider, model, now)

            # Save user message
            insert_message(
                chat_id, "user", message, now, provider=provider, model=model
            )
            logger.info(f"[NON-STREAMING] Saved user message to chat {chat_id}")

            # Generate and save assistant reply
            history = data.get("history") or []
            params = data.get("params") or {}
            reply_obj = generate_reply(provider, model, message, history, params=params)
            insert_message(
                chat_id,
                "assistant",
                reply_obj.reply,
                now,
                provider=provider,
                model=model,
            )
            logger.info(f"[NON-STREAMING] Saved assistant reply to chat {chat_id}")

            # Update chat timestamp and commit
            touch_chat(chat_id, now)
            commit()

            # Build response
            response_data = {
                "reply": reply_obj.reply,
                "chat_id": chat_id,
                "title": title or None,
            }
            for attr in ["warning", "error", "missing_key_for"]:
                if hasattr(reply_obj, attr) and getattr(reply_obj, attr):
                    response_data[attr] = getattr(reply_obj, attr)

            return jsonify(response_data)

        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception:  # pragma: no cover
            return jsonify({"error": "unexpected error"}), 500

    @app.post("/api/chat/stream")
    def api_chat_stream():
        """Streaming chat endpoint that streams tokens as they're generated.

        Expected JSON body:
            {
                "message": str,
                "chat_id": int (optional),
                "provider": str,
                "model": str,
                "title": str (optional)
            }

        Returns:
            Server-sent events stream with chat responses.
        """
        try:
            data = request.get_json(silent=True) or {}
            message, provider, model = _validate_chat_request(data)

            logger.info(f"[STREAMING] Received message: {message[:50]}...")
            logger.info(f"[STREAMING] Provider: {provider}, Model: {model}")

            chat_id = data.get("chat_id")
            title = (data.get("title") or "").strip()
            # Capture initial timestamp when request received
            request_ts = datetime.now(UTC).isoformat()

            # Generate default title if needed
            if not chat_id and not title:
                title = (
                    (message[:48] + "…") if len(message) > 49 else message or "New chat"
                )

            # Create or update chat and commit immediately for streaming
            chat_id = _create_or_update_chat(chat_id, title, provider, model, request_ts)
            commit()

            # Save user message with its own timestamp and immediately bump chat updated_at
            user_msg_ts = datetime.now(UTC).isoformat()
            insert_message(
                chat_id, "user", message, user_msg_ts, provider=provider, model=model
            )
            # Touch chat so it appears/updates in history sidebar right after the user sends a message
            touch_chat(chat_id, user_msg_ts)
            commit()
            logger.info(f"[STREAMING] Saved user message to chat {chat_id}")

            def generate() -> Generator[str, None, None]:
                """Generator function for streaming response."""
                try:
                    # Get history for context
                    history = data.get("history") or []

                    # Send initial metadata
                    yield f"data: {json.dumps({'type': 'metadata', 'chat_id': chat_id, 'title': title or None})}\n\n"

                    full_reply = ""

                    # Generate streaming reply
                    params = data.get("params") or {}
                    for chunk in generate_reply_stream(
                        provider, model, message, history, params=params
                    ):
                        if chunk.token:
                            full_reply += chunk.token
                            yield f"data: {json.dumps({'type': 'token', 'token': chunk.token})}\n\n"
                        elif chunk.error:
                            yield f"data: {json.dumps({'type': 'error', 'error': chunk.error, 'missing_key_for': chunk.missing_key_for})}\n\n"
                            return
                        elif chunk.warning:
                            yield f"data: {json.dumps({'type': 'warning', 'warning': chunk.warning})}\n\n"

                    # Save the complete reply to database in a new app context
                    if full_reply:
                        with app.app_context():
                            try:
                                # Use a fresh timestamp when assistant reply fully ready
                                assistant_ts = datetime.now(UTC).isoformat()
                                insert_message(
                                    chat_id,
                                    "assistant",
                                    full_reply,
                                    assistant_ts,
                                    provider=provider,
                                    model=model,
                                )
                                touch_chat(chat_id, assistant_ts)
                                commit()
                                logger.info(
                                    f"[STREAMING] Saved assistant reply to chat {chat_id}"
                                )
                            except Exception as e:
                                logger.error(f"[STREAMING] Error saving reply: {e}")

                    # Send completion signal
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"

                except Exception as e:
                    logger.error(f"[STREAMING] Error in generator: {str(e)}")
                    yield f"data: {json.dumps({'type': 'error', 'error': f'Stream error: {str(e)}'})}\n\n"

            return Response(
                generate(),
                mimetype="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Access-Control-Allow-Origin": "*",
                },
            )

        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:  # pragma: no cover
            logger.error(f"[STREAMING] Error in endpoint: {str(e)}")
            return jsonify({"error": "unexpected error"}), 500

    @app.get("/api/chats")
    def api_list_chats():
        """Get a list of all chats ordered by most recent activity.

        Returns:
            JSON response with list of chat metadata.
        """
        rows = list_chats()
        return jsonify(
            {
                "chats": [
                    {
                        "id": r["id"],
                        "title": r["title"],
                        "provider": r["provider"],
                        "model": r["model"],
                        "updated_at": r["updated_at"],
                    }
                    for r in rows
                ]
            }
        )

    @app.get("/api/chats/<int:chat_id>")
    def api_get_chat(chat_id: int):
        """Get a specific chat with all its messages.

        Args:
            chat_id: The chat ID to retrieve.

        Returns:
            JSON response with chat metadata and messages, or 404 if not found.
        """
        chat = db_get_chat(chat_id)
        if not chat:
            return jsonify({"error": "not found"}), 404

        messages = get_messages(chat_id)
        return jsonify(
            {
                "chat": {
                    "id": chat["id"],
                    "title": chat["title"],
                    "provider": chat["provider"],
                    "model": chat["model"],
                    "created_at": chat["created_at"],
                    "updated_at": chat["updated_at"],
                },
                "messages": [
                    {
                        "role": m["role"],
                        "content": m["content"],
                        "provider": m["provider"],
                        "model": m["model"],
                        "created_at": m["created_at"],
                    }
                    for m in messages
                ],
            }
        )

    @app.patch("/api/chats/<int:chat_id>")
    def api_update_chat(chat_id: int):
        """Update chat metadata (title, provider, model).

        Args:
            chat_id: The chat ID to update.

        Expected JSON body:
            {
                "title": str (optional),
                "provider": str (optional),
                "model": str (optional)
            }

        Returns:
            JSON response with success status or error.
        """
        if not db_get_chat(chat_id):
            return jsonify({"error": "not found"}), 404

        data = request.get_json(silent=True) or {}
        title = (data.get("title") or "").strip() or None
        provider = data.get("provider")
        model = data.get("model")

        if not any([title, provider, model]):
            return jsonify({"error": "no updates provided"}), 400

        now = datetime.now(UTC).isoformat()
        db_update_chat(chat_id, title=title, provider=provider, model=model, now=now)
        commit()
        return jsonify({"ok": True})

    @app.delete("/api/chats/<int:chat_id>")
    def api_delete_chat(chat_id: int):
        """Delete a chat and all its messages.

        Args:
            chat_id: The chat ID to delete.

        Returns:
            JSON response with success status or 404 if not found.
        """
        if not db_get_chat(chat_id):
            return jsonify({"error": "not found"}), 404

        delete_chat(chat_id)
        commit()
        return jsonify({"ok": True})

    # Settings: API keys -----------------------------------------------------

    def _get_env_path() -> str:
        """Get the path to the .env file for environment variable storage.

        Returns:
            Path to the .env file.
        """
        return app.config.get("ENV_PATH", os.path.join(app.root_path, ".env"))

    def _load_env_into_process() -> None:
        """Ensure process environment reflects file updates."""
        load_dotenv(_get_env_path(), override=True)

    @app.get("/api/keys")
    def api_get_keys():
        """Get current API keys for all providers.

        Returns:
            JSON response with current API key values (or empty strings if not set).
        """
        # Prefer file values; fall back to current process env
        values = dotenv_values(_get_env_path())
        openai_key = values.get("OPENAI_API_KEY") if values else None
        gemini_key = values.get("GEMINI_API_KEY") if values else None

        # If not in file, try process env
        openai_key = openai_key or os.getenv("OPENAI_API_KEY", "")
        gemini_key = gemini_key or os.getenv("GEMINI_API_KEY", "")

        return jsonify(
            {
                "openai": openai_key,
                "gemini": gemini_key,
            }
        )

    @app.put("/api/keys")
    def api_put_keys():
        """Set or update API keys for providers.

        Expected JSON body:
            {
                "openai": str (optional),
                "gemini": str (optional)
            }

        Returns:
            JSON response with update status and the keys that were updated.
        """
        data = request.get_json(silent=True) or {}
        env_file = _get_env_path()
        os.makedirs(os.path.dirname(env_file), exist_ok=True)

        updated: dict[str, Optional[str]] = {}
        key_mapping = [("OPENAI_API_KEY", "openai"), ("GEMINI_API_KEY", "gemini")]

        for env_key, body_key in key_mapping:
            if body_key in data:
                value = data.get(body_key)
                if value is None or str(value).strip() == "":
                    # Remove the key
                    try:
                        unset_key(env_file, env_key)
                    except Exception:
                        pass
                    os.environ.pop(env_key, None)
                    updated[body_key] = None
                else:
                    # Set the key
                    set_key(env_file, env_key, str(value), quote_mode="never")
                    os.environ[env_key] = str(value)
                    updated[body_key] = str(value)

        _load_env_into_process()
        return jsonify({"ok": True, "updated": updated})

    @app.delete("/api/keys/<provider>")
    def api_delete_key(provider: str):
        """Delete API key for a specific provider.

        Args:
            provider: Provider name ('openai' or 'gemini').

        Returns:
            JSON response with success status or error if provider is unknown.
        """
        key_mapping = {"openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY"}
        env_key = key_mapping.get(provider.lower())

        if not env_key:
            return jsonify({"error": "unknown provider"}), 400

        env_file = _get_env_path()
        try:
            unset_key(env_file, env_key)
        except Exception:
            pass

        os.environ.pop(env_key, None)
        _load_env_into_process()
        return jsonify({"ok": True})

    # Provider/model favorites & defaults ------------------------------------

    # Allow tests (or other environments) to override the providers.json path
    # via environment variable (must be decided before the helper closures capture it)
    PROVIDERS_JSON_PATH = os.environ.get(
        "PROVIDERS_JSON_PATH", os.path.join(app.root_path, "static", "providers.json")
    )

    def _load_providers_json() -> dict:
        try:
            with open(PROVIDERS_JSON_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return {"providers": [], "favorites": [], "default": {"provider": None, "model": None}}
        except Exception:
            return {"providers": [], "favorites": [], "default": {"provider": None, "model": None}}

    def _write_providers_json(data: dict) -> None:
        os.makedirs(os.path.dirname(PROVIDERS_JSON_PATH), exist_ok=True)
        tmp_path = PROVIDERS_JSON_PATH + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, PROVIDERS_JSON_PATH)

    def _get_dynamic_providers_config() -> dict:
        """Get providers config with dynamic Ollama models if available."""
        # Load static providers from JSON
        data = _load_providers_json()
        providers = data.get("providers", []).copy()
        
        # Try to add Ollama dynamically
        from chat import is_ollama_available, start_ollama_server, get_ollama_models
        
        if is_ollama_available():
            # Try to start Ollama server if not running
            start_ollama_server()
            
            # Get available models
            models = get_ollama_models()
            if models:
                # Add Ollama provider with current models
                ollama_provider = {
                    "id": "ollama",
                    "name": "Ollama (Local)",
                    "models": models
                }
                providers.append(ollama_provider)
        
        # Return updated config without modifying the file
        return {
            "providers": providers,
            "favorites": data.get("favorites", []),
            "default": data.get("default", {"provider": None, "model": None})
        }

    def _validate_provider_model(provider: str, model: str) -> bool:
        data = _load_providers_json()
        for p in data.get("providers", []):
            if p.get("id") == provider and model in (p.get("models") or []):
                return True
        return False

    @app.get("/api/favorites")
    def api_get_favorites():
        data = _load_providers_json()
        return jsonify({
            "favorites": data.get("favorites", []),
            "default": data.get("default", {})
        })

    @app.post("/api/favorites")
    def api_add_favorite():
        body = request.get_json(silent=True) or {}
        provider = (body.get("provider") or "").strip()
        model = (body.get("model") or "").strip()
        if not provider or not model:
            return jsonify({"error": "provider and model required"}), 400
        if not _validate_provider_model(provider, model):
            return jsonify({"error": "unknown provider/model"}), 400
        data = _load_providers_json()
        favs = data.setdefault("favorites", [])
        key = f"{provider}:{model}"
        if key not in favs:
            favs.append(key)
        _write_providers_json(data)
        return jsonify({"ok": True, "favorites": favs})

    @app.delete("/api/favorites")
    def api_remove_favorite():
        provider = (request.args.get("provider") or "").strip()
        model = (request.args.get("model") or "").strip()
        if not provider or not model:
            return jsonify({"error": "provider and model required"}), 400
        data = _load_providers_json()
        key = f"{provider}:{model}"
        favs = data.setdefault("favorites", [])
        if key in favs:
            favs.remove(key)
        _write_providers_json(data)
        return jsonify({"ok": True, "favorites": favs})

    @app.put("/api/default-model")
    def api_set_default_model():
        body = request.get_json(silent=True) or {}
        provider = (body.get("provider") or "").strip()
        model = (body.get("model") or "").strip()
        if not provider or not model:
            return jsonify({"error": "provider and model required"}), 400
        if not _validate_provider_model(provider, model):
            return jsonify({"error": "unknown provider/model"}), 400
        data = _load_providers_json()
        data["default"] = {"provider": provider, "model": model}
        _write_providers_json(data)
        return jsonify({"ok": True, "default": data["default"]})

    @app.get("/api/providers-config")
    def api_get_providers_config():
        return jsonify(_get_dynamic_providers_config())

    # Dynamic model parameter metadata --------------------------------------
    @app.get("/api/model-config")
    def api_model_config():
        """Return configurable parameter schema for a provider/model.

        Query params:
            provider: provider id (required)
            model: model id/name (required)

        Response JSON shape:
            {
              "provider": str,
              "model": str,
              "params": [
                 { "name": "temperature", "type": "number", "min":0, "max":2, "step":0.01, "default":1.0, "label": "Temperature" },
                 ...
              ]
            }
        """
        provider = (request.args.get("provider") or "").strip().lower()
        model = (request.args.get("model") or "").strip()
        if not provider or not model:
            return jsonify({"error": "provider and model required"}), 400

        # Basic heuristics per provider/model family. Real implementation could introspect SDK.
        params: list[dict] = []
        if provider == "openai":
            # Reasoning models (o3*) allow reasoning_effort; others standard chat params
            base = [
                {"name": "temperature", "type": "number", "min": 0, "max": 2, "step": 0.01, "default": 1.0, "label": "Temperature"},
                {"name": "top_p", "type": "number", "min": 0, "max": 1, "step": 0.01, "default": 1.0, "label": "Top P"},
                {"name": "max_tokens", "type": "integer", "min": 1, "max": 8192, "step": 1, "default": 2048, "label": "Max Tokens"},
                {"name": "presence_penalty", "type": "number", "min": -2, "max": 2, "step": 0.01, "default": 0.0, "label": "Presence Penalty"},
                {"name": "frequency_penalty", "type": "number", "min": -2, "max": 2, "step": 0.01, "default": 0.0, "label": "Frequency Penalty"},
            ]
            # Additional advanced params (exposed only for GPT-5 family to reduce clutter elsewhere)
            if model.lower().startswith("gpt-5"):
                base.extend([
                    {"name": "seed", "type": "integer", "min": 0, "max": 2147483647, "step": 1, "default": 0, "label": "Seed"},
                    {"name": "stop", "type": "string", "default": "", "label": "Stop Sequences (comma)"},
                    {"name": "response_format", "type": "select", "options": ["text", "json_object"], "default": "text", "label": "Response Format"},
                    {"name": "thinking", "type": "select", "options": ["none", "light", "deep"], "default": "none", "label": "Thinking Mode"},
                    {"name": "thinking_budget_tokens", "type": "integer", "min": 32, "max": 8192, "step": 1, "default": 512, "label": "Thinking Budget"},
                ])
            if model.lower().startswith("o3"):
                base.append({
                    "name": "reasoning_effort", "type": "select", "options": ["low", "medium", "high"], "default": "low", "label": "Reasoning Effort"
                })
            params = base
        elif provider == "gemini":
            params = [
                {"name": "temperature", "type": "number", "min": 0, "max": 2, "step": 0.01, "default": 1.0, "label": "Temperature"},
                {"name": "top_p", "type": "number", "min": 0, "max": 1, "step": 0.01, "default": 1.0, "label": "Top P"},
                {"name": "top_k", "type": "integer", "min": 1, "max": 100, "step": 1, "default": 40, "label": "Top K"},
                {"name": "max_output_tokens", "type": "integer", "min": 16, "max": 8192, "step": 1, "default": 1024, "label": "Max Output Tokens"},
                {"name": "web_search", "type": "boolean", "default": False, "label": "Web Search"},
            ]
        elif provider == "ollama":
            params = [
                {"name": "temperature", "type": "number", "min": 0, "max": 2, "step": 0.01, "default": 0.8, "label": "Temperature"},
                {"name": "top_p", "type": "number", "min": 0, "max": 1, "step": 0.01, "default": 0.9, "label": "Top P"},
                {"name": "top_k", "type": "integer", "min": 1, "max": 100, "step": 1, "default": 40, "label": "Top K"},
                {"name": "max_tokens", "type": "integer", "min": 1, "max": 8192, "step": 1, "default": 2048, "label": "Max Tokens"},
            ]
        elif provider == "ollama":
            params = [
                {"name": "temperature", "type": "number", "min": 0, "max": 2, "step": 0.01, "default": 0.8, "label": "Temperature"},
                {"name": "top_p", "type": "number", "min": 0, "max": 1, "step": 0.01, "default": 0.9, "label": "Top P"},
                {"name": "top_k", "type": "integer", "min": 1, "max": 100, "step": 1, "default": 40, "label": "Top K"},
                {"name": "max_tokens", "type": "integer", "min": 1, "max": 8192, "step": 1, "default": 2048, "label": "Max Tokens"},
            ]
        else:
            return jsonify({"error": "unknown provider"}), 400

        return jsonify({"provider": provider, "model": model, "params": params})

    return app


def _initialize_ollama():
    """Initialize Ollama server and update providers.json at startup."""
    try:
        if is_ollama_available():
            print("Ollama detected, attempting to start server...")
            if start_ollama_server():
                print("Ollama server started successfully.")
                # Update providers.json with current models
                from chat import get_ollama_models
                models = get_ollama_models()
                print(f"Found {len(models)} Ollama models: {models}")
            else:
                print("Failed to start Ollama server.")
        else:
            print("Ollama not available on this system.")
    except Exception as e:
        print(f"Error initializing Ollama: {e}")


# Create the main application instance
app = create_app()

# Initialize Ollama on startup
_initialize_ollama()


if __name__ == "__main__":
    # Run the development server
    app.run(debug=True, host="127.0.0.1", port=5000)
