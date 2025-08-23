"""Main Flask application for the Omni Chat application."""

import json
import logging
import os
from datetime import datetime, UTC
from typing import Optional

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
    create_project,
    list_projects,
    get_project,
    delete_project,
    add_chat_to_project,
    remove_chat_from_project,
    list_chats_by_project,
)
from chat import generate_reply
from utils import (
    validate_chat_request,
    generate_chat_title,
    EnvironmentManager,
    ProvidersConfigManager,
    create_or_update_chat,
    initialize_ollama_with_app,
)


def create_app() -> Flask:
    """Application factory to create and configure the Flask app.

    Returns:
        Configured Flask application instance.
    """
    app = Flask(__name__)

    # Set up logging
    logging.basicConfig(level=logging.WARNING)
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
    
    # Allow tests (or other environments) to override the providers.json path
    providers_json_path = os.environ.get(
        "PROVIDERS_JSON_PATH", os.path.join(app.root_path, "static", "providers.json")
    )
    providers_manager = ProvidersConfigManager(providers_json_path)

    def get_env_manager():
        """Get the EnvironmentManager instance, creating it lazily with current config."""
        if not hasattr(get_env_manager, '_instance') or get_env_manager._config_path != app.config["ENV_PATH"]:
            get_env_manager._instance = EnvironmentManager(app.config["ENV_PATH"])
            get_env_manager._config_path = app.config["ENV_PATH"]
        return get_env_manager._instance

    @app.route("/")
    def home():
        """Render the main chat interface."""
        return render_template("index.html")

    @app.post("/api/chat")
    def api_chat():
        """Chat endpoint that stores messages and generates a reply.

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
            message, provider, model = validate_chat_request(data)

            chat_id = data.get("chat_id")
            title = (data.get("title") or "").strip()
            now = datetime.now(UTC).isoformat()

            # Generate default title if needed
            if not chat_id and not title:
                title = generate_chat_title(message)

            # Create or update chat
            chat_id = create_or_update_chat(chat_id, title, provider, model, now)

            # Save user message
            insert_message(
                chat_id, "user", message, now, provider=provider, model=model
            )

            # Generate and save assistant reply
            history = data.get("history") or []
            params = data.get("params") or {}
            
            logger.info(f"[API] Calling generate_reply for {provider}/{model}")
            logger.info(f"[API] Message length: {len(message)} chars")
            logger.info(f"[API] History length: {len(history)} messages")
            logger.info(f"[API] Params: {params}")
            
            reply_obj = generate_reply(provider, model, message, history, params=params)
            
            logger.info(f"[API] Reply received - length: {len(reply_obj.reply)} chars")
            if reply_obj.error:
                logger.warning(f"[API] Reply contains error: {reply_obj.error}")
            if reply_obj.warning:
                logger.info(f"[API] Reply contains warning: {reply_obj.warning}")
                
            insert_message(
                chat_id,
                "assistant",
                reply_obj.reply,
                now,
                provider=provider,
                model=model,
            )

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

    @app.get("/api/chats/count")
    def api_count_all_history():
        """Get count of all chats and messages in the database.
        
        Returns:
            JSON response with counts of chats and messages.
        """
        from database import count_all_history
        
        counts = count_all_history()
        return jsonify(counts)

    @app.delete("/api/chats")
    def api_delete_all_history():
        """Delete all chats and messages from the database.
        
        Returns:
            JSON response with counts of deleted chats and messages.
        """
        from database import delete_all_history
        
        deleted_counts = delete_all_history()
        commit()
        return jsonify({"ok": True, "deleted": deleted_counts})

    # Settings: API keys -----------------------------------------------------

    @app.get("/api/keys")
    def api_get_keys():
        """Get current API keys for all providers.

        Returns:
            JSON response with current API key values (or empty strings if not set).
        """
        return jsonify(get_env_manager().get_api_keys())

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
        updated = get_env_manager().update_api_keys(data)
        return jsonify({"ok": True, "updated": updated})

    @app.delete("/api/keys/<provider>")
    def api_delete_key(provider: str):
        """Delete API key for a specific provider.

        Args:
            provider: Provider name ('openai' or 'gemini').

        Returns:
            JSON response with success status or error if provider is unknown.
        """
        success = get_env_manager().delete_api_key(provider)
        if not success:
            return jsonify({"error": "unknown provider"}), 400
        return jsonify({"ok": True})

    # Provider/model favorites & defaults ------------------------------------

    @app.get("/api/favorites")
    def api_get_favorites():
        data = providers_manager.load_providers_json()
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
        if not providers_manager.validate_provider_model(provider, model):
            return jsonify({"error": "unknown provider/model"}), 400
        data = providers_manager.load_providers_json()
        favs = data.setdefault("favorites", [])
        key = f"{provider}:{model}"
        if key not in favs:
            favs.append(key)
        providers_manager.write_providers_json(data)
        return jsonify({"ok": True, "favorites": favs})

    @app.delete("/api/favorites")
    def api_remove_favorite():
        provider = (request.args.get("provider") or "").strip()
        model = (request.args.get("model") or "").strip()
        if not provider or not model:
            return jsonify({"error": "provider and model required"}), 400
        data = providers_manager.load_providers_json()
        key = f"{provider}:{model}"
        favs = data.setdefault("favorites", [])
        if key in favs:
            favs.remove(key)
        providers_manager.write_providers_json(data)
        return jsonify({"ok": True, "favorites": favs})

    # Blacklist management --------------------------------------------------
    @app.get("/api/blacklist")
    def api_get_blacklist():
        """Get current blacklisted words."""
        data = providers_manager.load_providers_json()
        return jsonify({"blacklist": data.get("blacklist", [])})

    @app.post("/api/blacklist")
    def api_add_blacklist_word():
        """Add a word to the blacklist."""
        body = request.get_json(silent=True) or {}
        word = (body.get("word") or "").strip().lower()
        if not word:
            return jsonify({"error": "word is required"}), 400
        data = providers_manager.load_providers_json()
        blacklist = data.setdefault("blacklist", [])
        if word not in blacklist:
            blacklist.append(word)
        providers_manager.write_providers_json(data)
        response = jsonify({"ok": True, "blacklist": blacklist})
        response.headers["X-Blacklist-Updated"] = "true"
        return response

    @app.delete("/api/blacklist")
    def api_remove_blacklist_word():
        """Remove a word from the blacklist."""
        word = (request.args.get("word") or "").strip().lower()
        if not word:
            return jsonify({"error": "word is required"}), 400
        data = providers_manager.load_providers_json()
        blacklist = data.setdefault("blacklist", [])
        if word in blacklist:
            blacklist.remove(word)
        providers_manager.write_providers_json(data)
        response = jsonify({"ok": True, "blacklist": blacklist})
        response.headers["X-Blacklist-Updated"] = "true"
        return response

    @app.put("/api/default-model")
    def api_set_default_model():
        body = request.get_json(silent=True) or {}
        provider = (body.get("provider") or "").strip()
        model = (body.get("model") or "").strip()
        if not provider or not model:
            return jsonify({"error": "provider and model required"}), 400
        if not providers_manager.validate_provider_model(provider, model):
            return jsonify({"error": "unknown provider/model"}), 400
        data = providers_manager.load_providers_json()
        data["default"] = {"provider": provider, "model": model}
        providers_manager.write_providers_json(data)
        return jsonify({"ok": True, "default": data["default"]})

    @app.get("/api/providers-config")
    def api_get_providers_config():
        return jsonify(providers_manager.load_providers_json())

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
        else:
            return jsonify({"error": "unknown provider"}), 400

        return jsonify({"provider": provider, "model": model, "params": params})

    # Project management endpoints ------------------------------------------

    @app.get("/api/projects")
    def api_list_projects():
        """Get all projects ordered by most recent activity."""
        try:
            projects = list_projects()
            return jsonify({"projects": projects})
        except Exception:  # pragma: no cover
            return jsonify({"error": "failed to load projects"}), 500

    @app.post("/api/projects")
    def api_create_project():
        """Create a new project.
        
        Expected JSON body:
            {
                "name": str
            }
        """
        try:
            data = request.get_json(silent=True) or {}
            name = (data.get("name") or "").strip()
            if not name:
                return jsonify({"error": "name is required"}), 400
            
            now = datetime.now(UTC).isoformat()
            project_id = create_project(name, now)
            commit()
            
            project = get_project(project_id)
            return jsonify({"project": project})
        except Exception:  # pragma: no cover
            return jsonify({"error": "failed to create project"}), 500

    @app.get("/api/projects/<int:project_id>")
    def api_get_project(project_id: int):
        """Get a single project with its chats."""
        try:
            project = get_project(project_id)
            if not project:
                return jsonify({"error": "project not found"}), 404
            
            chats = list_chats_by_project(project_id)
            return jsonify({"project": project, "chats": chats})
        except Exception:  # pragma: no cover
            return jsonify({"error": "failed to load project"}), 500

    @app.delete("/api/projects/<int:project_id>")
    def api_delete_project(project_id: int):
        """Delete a project and unassign all its chats."""
        try:
            project = get_project(project_id)
            if not project:
                return jsonify({"error": "project not found"}), 404
            
            delete_project(project_id)
            commit()
            return jsonify({"ok": True})
        except Exception:  # pragma: no cover
            return jsonify({"error": "failed to delete project"}), 500

    @app.post("/api/chats/<int:chat_id>/project")
    def api_add_chat_to_project(chat_id: int):
        """Add a chat to a project.
        
        Expected JSON body:
            {
                "project_id": int
            }
        """
        try:
            data = request.get_json(silent=True) or {}
            project_id = data.get("project_id")
            if not isinstance(project_id, int):
                return jsonify({"error": "project_id is required"}), 400
            
            # Verify chat and project exist
            chat = db_get_chat(chat_id)
            if not chat:
                return jsonify({"error": "chat not found"}), 404
            
            project = get_project(project_id)
            if not project:
                return jsonify({"error": "project not found"}), 404
            
            now = datetime.now(UTC).isoformat()
            add_chat_to_project(chat_id, project_id, now)
            commit()
            
            return jsonify({"ok": True})
        except Exception:  # pragma: no cover
            return jsonify({"error": "failed to add chat to project"}), 500

    @app.delete("/api/chats/<int:chat_id>/project")
    def api_remove_chat_from_project(chat_id: int):
        """Remove a chat from its project."""
        try:
            chat = db_get_chat(chat_id)
            if not chat:
                return jsonify({"error": "chat not found"}), 404
            
            now = datetime.now(UTC).isoformat()
            remove_chat_from_project(chat_id, now)
            commit()
            
            return jsonify({"ok": True})
        except Exception:  # pragma: no cover
            return jsonify({"error": "failed to remove chat from project"}), 500

    @app.get("/api/chats/by-project")
    def api_list_chats_by_project():
        """Get chats filtered by project.
        
        Query params:
            project_id: int (optional) - if provided, returns chats for that project;
                       if not provided or null, returns unassigned chats
        """
        try:
            project_id = request.args.get("project_id")
            if project_id is not None:
                try:
                    project_id = int(project_id)
                except ValueError:
                    return jsonify({"error": "invalid project_id"}), 400
            
            chats = list_chats_by_project(project_id)
            return jsonify({"chats": chats})
        except Exception:  # pragma: no cover
            return jsonify({"error": "failed to load chats"}), 500

    return app


# Create the main application instance
app = create_app()

# Initialize Ollama and update providers.json on startup
initialize_ollama_with_app(app)


if __name__ == "__main__":
    # Run the development server
    app.run(debug=True, host="127.0.0.1", port=5000)
