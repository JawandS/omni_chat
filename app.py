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
from chat import generate_reply, generate_reply_stream


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


def _create_or_update_chat(chat_id: Optional[int], title: str, provider: str, model: str, now: str) -> int:
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
    if app.config.get('TESTING') and not os.environ.get('PYTEST_CURRENT_TEST'):
        logger.warning("App configured for testing but not running under pytest - this may affect production resources!")

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
                title = (message[:48] + "…") if len(message) > 49 else message or "New chat"

            # Create or update chat
            chat_id = _create_or_update_chat(chat_id, title, provider, model, now)

            # Save user message
            insert_message(chat_id, 'user', message, now, provider=provider, model=model)
            logger.info(f"[NON-STREAMING] Saved user message to chat {chat_id}")

            # Generate and save assistant reply
            history = data.get("history") or []
            reply_obj = generate_reply(provider, model, message, history)
            insert_message(chat_id, 'assistant', reply_obj.reply, now, provider=provider, model=model)
            logger.info(f"[NON-STREAMING] Saved assistant reply to chat {chat_id}")

            # Update chat timestamp and commit
            touch_chat(chat_id, now)
            commit()

            # Build response
            response_data = {"reply": reply_obj.reply, "chat_id": chat_id, "title": title or None}
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
            now = datetime.now(UTC).isoformat()

            # Generate default title if needed
            if not chat_id and not title:
                title = (message[:48] + "…") if len(message) > 49 else message or "New chat"

            # Create or update chat and commit immediately for streaming
            chat_id = _create_or_update_chat(chat_id, title, provider, model, now)
            commit()

            # Save user message and commit
            insert_message(chat_id, 'user', message, now, provider=provider, model=model)
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
                    for chunk in generate_reply_stream(provider, model, message, history):
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
                                insert_message(chat_id, 'assistant', full_reply, now, provider=provider, model=model)
                                touch_chat(chat_id, now)
                                commit()
                                logger.info(f"[STREAMING] Saved assistant reply to chat {chat_id}")
                            except Exception as e:
                                logger.error(f"[STREAMING] Error saving reply: {e}")
                    
                    # Send completion signal
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    
                except Exception as e:
                    logger.error(f"[STREAMING] Error in generator: {str(e)}")
                    yield f"data: {json.dumps({'type': 'error', 'error': f'Stream error: {str(e)}'})}\n\n"

            return Response(generate(), mimetype='text/event-stream', headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*',
            })
            
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
        return jsonify({
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
        })

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
        return jsonify({
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
                    "created_at": m["created_at"]
                }
                for m in messages
            ],
        })

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
        
        return jsonify({
            "openai": openai_key,
            "gemini": gemini_key,
        })

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

    return app


# Create the main application instance
app = create_app()


if __name__ == "__main__":
    # Run the development server
    app.run(debug=True, host="127.0.0.1", port=5000)
