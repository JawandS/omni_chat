from datetime import datetime, UTC
from flask import Flask, render_template, request, jsonify

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
from chat import generate_reply


def create_app() -> Flask:
    """Application factory to create and configure the Flask app."""
    app = Flask(__name__)

    # Configure DB integration (path, teardown)
    db_init_app(app)

    with app.app_context():
        init_db()

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
            if not message:
                return jsonify({"error": "message is required"}), 400

            provider = (data.get("provider") or "unknown").strip()
            model = (data.get("model") or "unknown").strip()
            title = (data.get("title") or "").strip()
            chat_id = data.get("chat_id")

            now = datetime.now(UTC).isoformat()

            # Create chat if needed
            if not chat_id:
                if not title:
                    title = (message[:48] + "…") if len(message) > 49 else message or "New chat"
                chat_id = create_chat(title, provider, model, now)
            else:
                # Update provider/model if changed
                update_chat_meta(chat_id, provider, model, now)

            # Save user message
            insert_message(chat_id, 'user', message, now)

            # Generate and save assistant reply (placeholder echo)
            reply_obj = generate_reply(provider, model, message)
            reply = reply_obj.reply
            insert_message(chat_id, 'assistant', reply, now)

            # Touch chat updated_at
            touch_chat(chat_id, now)
            commit()

            return jsonify({"reply": reply, "chat_id": chat_id, "title": title or None})
        except Exception:  # pragma: no cover - keep placeholder simple
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
                {"role": m["role"], "content": m["content"], "created_at": m["created_at"]} for m in msgs
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

    return app


app = create_app()


if __name__ == "__main__":
    # Run the development server
    app.run(debug=True, host="127.0.0.1", port=5000)
