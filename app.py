from datetime import datetime, UTC
from flask import Flask, render_template, request, jsonify, Response, stream_template
import os
import json
import logging
from typing import Optional, Generator
from dotenv import load_dotenv, set_key, unset_key, dotenv_values

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


def create_app() -> Flask:
    """Application factory to create and configure the Flask app."""
    app = Flask(__name__)

    # Set up logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Configure DB integration (path, teardown)
    db_init_app(app)

    with app.app_context():
        init_db()

    # Default path to .env can be overridden in tests via app.config['ENV_PATH']
    app.config.setdefault("ENV_PATH", os.path.join(app.root_path, ".env"))

    @app.route("/")
    def home():
        return render_template("index.html")

    @app.post("/api/chat")
    def api_chat():
        """Chat endpoint that stores messages and echoes a reply.

        Expected JSON body:
        { message: str, chat_id?: int, provider: str, model: str, title?: str }
        """
        try:
            data = request.get_json(silent=True) or {}
            message = (data.get("message") or "").strip()
            logger.info(f"[NON-STREAMING] Received message: {message[:50]}...")
            
            if not message:
                return jsonify({"error": "message is required"}), 400

            provider = (data.get("provider") or "unknown").strip()
            model = (data.get("model") or "unknown").strip()
            title = (data.get("title") or "").strip()
            chat_id = data.get("chat_id")

            logger.info(f"[NON-STREAMING] Provider: {provider}, Model: {model}, Chat ID: {chat_id}")

            now = datetime.now(UTC).isoformat()

            # Create chat if needed
            if not chat_id:
                if not title:
                    title = (message[:48] + "…") if len(message) > 49 else message or "New chat"
                chat_id = create_chat(title, provider, model, now)
                logger.info(f"[NON-STREAMING] Created new chat with ID: {chat_id}")
            else:
                # Update provider/model if changed
                update_chat_meta(chat_id, provider, model, now)

            # Save user message (store provider/model snapshot on message for auditability)
            insert_message(chat_id, 'user', message, now, provider=provider, model=model)
            logger.info(f"[NON-STREAMING] Saved user message to chat {chat_id}")

            # Generate and save assistant reply (OpenAI/Gemini if configured). Pass history along.
            history = data.get("history") or []
            try:
                reply_obj = generate_reply(provider, model, message, history)
            except ValueError as e:
                return jsonify({"error": str(e)}), 400
            reply = reply_obj.reply
            insert_message(chat_id, 'assistant', reply, now, provider=provider, model=model)
            logger.info(f"[NON-STREAMING] Saved assistant reply to chat {chat_id}")

            # Touch chat updated_at
            touch_chat(chat_id, now)
            commit()

            resp_body = {"reply": reply, "chat_id": chat_id, "title": title or None}
            if getattr(reply_obj, "warning", None):
                resp_body["warning"] = reply_obj.warning
            if getattr(reply_obj, "error", None):
                resp_body["error"] = reply_obj.error
            if getattr(reply_obj, "missing_key_for", None):
                resp_body["missing_key_for"] = reply_obj.missing_key_for
            return jsonify(resp_body)
        except Exception:  # pragma: no cover - keep placeholder simple
            return jsonify({"error": "unexpected error"}), 500

    @app.post("/api/chat/stream")
    def api_chat_stream():
        """Streaming chat endpoint that streams tokens as they're generated.

        Expected JSON body:
        { message: str, chat_id?: int, provider: str, model: str, title?: str }
        """
        try:
            data = request.get_json(silent=True) or {}
            message = (data.get("message") or "").strip()
            logger.info(f"[STREAMING] Received message: {message[:50]}...")
            
            if not message:
                return jsonify({"error": "message is required"}), 400

            provider = (data.get("provider") or "unknown").strip()
            model = (data.get("model") or "unknown").strip()
            title = (data.get("title") or "").strip()
            chat_id = data.get("chat_id")

            logger.info(f"[STREAMING] Provider: {provider}, Model: {model}, Chat ID: {chat_id}")

            now = datetime.now(UTC).isoformat()

            # Create chat if needed and commit immediately
            if not chat_id:
                if not title:
                    title = (message[:48] + "…") if len(message) > 49 else message or "New chat"
                chat_id = create_chat(title, provider, model, now)
                commit()  # Commit the chat creation immediately
                logger.info(f"[STREAMING] Created new chat with ID: {chat_id}")
            else:
                # Update provider/model if changed
                update_chat_meta(chat_id, provider, model, now)
                commit()  # Commit the metadata update

            # Save user message and commit
            insert_message(chat_id, 'user', message, now, provider=provider, model=model)
            commit()  # Commit the user message
            logger.info(f"[STREAMING] Saved user message to chat {chat_id}")

            def generate() -> Generator[str, None, None]:
                """Generator function for streaming response."""
                with app.app_context():
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
                        
                        # Save the complete reply to database
                        if full_reply:
                            insert_message(chat_id, 'assistant', full_reply, now, provider=provider, model=model)
                            touch_chat(chat_id, now)
                            commit()
                            logger.info(f"[STREAMING] Saved assistant reply to chat {chat_id}")
                        
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
        except Exception as e:  # pragma: no cover - keep placeholder simple
            logger.error(f"[STREAMING] Error in endpoint: {str(e)}")
            return jsonify({"error": "unexpected error"}), 500

    @app.get("/api/chats")
    def api_list_chats():
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
        chat = db_get_chat(chat_id)
        if not chat:
            return jsonify({"error": "not found"}), 404
        msgs = get_messages(chat_id)
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
                {"role": m["role"], "content": m["content"], "provider": m["provider"], "model": m["model"], "created_at": m["created_at"]} for m in msgs
            ],
        })

    @app.patch("/api/chats/<int:chat_id>")
    def api_update_chat(chat_id: int):
        data = request.get_json(silent=True) or {}
        title = (data.get("title") or "").strip()
        provider = data.get("provider")
        model = data.get("model")
        if not any([title, provider, model]):
            return jsonify({"error": "no updates provided"}), 400
        now = datetime.now(UTC).isoformat()

        chat = db_get_chat(chat_id)
        if not chat:
            return jsonify({"error": "not found"}), 404
        db_update_chat(chat_id, title=title or None, provider=provider, model=model, now=now)
        commit()
        return jsonify({"ok": True})

    @app.delete("/api/chats/<int:chat_id>")
    def api_delete_chat(chat_id: int):
        chat = db_get_chat(chat_id)
        if not chat:
            return jsonify({"error": "not found"}), 404
        delete_chat(chat_id)
        commit()
        return jsonify({"ok": True})

    # Settings: API keys -----------------------------------------------------
    def _env_path() -> str:
        # Use configurable path for tests; default to project .env
        return app.config.get("ENV_PATH", os.path.join(app.root_path, ".env"))

    def _load_env_into_process() -> None:
        # Ensure process env reflects file updates
        load_dotenv(_env_path(), override=True)

    @app.get("/api/keys")
    def api_get_keys():
        # Prefer file values; fall back to current process env
        values = dotenv_values(_env_path())
        openai = values.get("OPENAI_API_KEY") if values else None
        gemini = values.get("GEMINI_API_KEY") if values else None
        # If not in file, try process env
        openai = openai or os.getenv("OPENAI_API_KEY")
        gemini = gemini or os.getenv("GEMINI_API_KEY")
        return jsonify({
            "openai": openai or "",
            "gemini": gemini or "",
        })

    @app.put("/api/keys")
    def api_put_keys():
        data = request.get_json(silent=True) or {}
        env_file = _env_path()
        os.makedirs(os.path.dirname(env_file), exist_ok=True)
        updated: dict[str, Optional[str]] = {}
        for k_env, body_key in (("OPENAI_API_KEY", "openai"), ("GEMINI_API_KEY", "gemini")):
            if body_key in data:
                value = data.get(body_key)
                if value is None or str(value).strip() == "":
                    try:
                        unset_key(env_file, k_env)
                    except Exception:
                        pass
                    os.environ.pop(k_env, None)
                    updated[body_key] = None
                else:
                    set_key(env_file, k_env, str(value), quote_mode="never")
                    os.environ[k_env] = str(value)
                    updated[body_key] = str(value)
        _load_env_into_process()
        return jsonify({"ok": True, "updated": updated})

    @app.delete("/api/keys/<provider>")
    def api_delete_key(provider: str):
        mapping = {"openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY"}
        key = mapping.get(provider.lower())
        if not key:
            return jsonify({"error": "unknown provider"}), 400
        env_file = _env_path()
        try:
            unset_key(env_file, key)
        except Exception:
            pass
        os.environ.pop(key, None)
        _load_env_into_process()
        return jsonify({"ok": True})

    return app


app = create_app()


if __name__ == "__main__":
    # Run the development server
    app.run(debug=True, host="127.0.0.1", port=5000)
