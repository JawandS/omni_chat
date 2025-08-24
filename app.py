"""
Main Flask application for the Omni Chat application.

This module contains the Flask application factory and all route handlers for the
Omni Chat web interface. It provides:

- Chat endpoint for AI model conversations
- Chat management (CRUD operations)
- Project organization features
- Task scheduling functionality
- Email notifications
- API key management
- Provider configuration management

The application uses SQLite for data persistence and supports multiple AI providers
including OpenAI, Gemini, and Ollama through a unified interface.

Key Components:
    - create_app(): Application factory function
    - Chat routes: Handle conversation endpoints
    - Project routes: Manage chat organization
    - Task routes: Schedule recurring AI tasks
    - Configuration routes: Manage API keys and settings

Security:
    - Environment-based configuration
    - Isolated test database for testing
    - Input validation for all endpoints
    - Safe HTML escaping in templates
"""

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
    create_task,
    list_tasks,
    get_task,
    update_task,
    delete_task as db_delete_task,
    update_task_status,
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
from email_service import send_task_email


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
        if (
            not hasattr(get_env_manager, "_instance")
            or get_env_manager._config_path != app.config["ENV_PATH"]
        ):
            get_env_manager._instance = EnvironmentManager(app.config["ENV_PATH"])
            get_env_manager._config_path = app.config["ENV_PATH"]
        return get_env_manager._instance

    @app.route("/")
    def home():
        """Render the main chat interface."""
        return render_template("index.html")

    @app.route("/schedule")
    def schedule():
        """Render the task scheduling interface."""
        return render_template("schedule.html")

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

    # Email configuration endpoints ------------------------------------------

    @app.get("/api/email/config")
    def api_get_email_config():
        """Get current email configuration.

        Returns:
            JSON response with email configuration (passwords are masked).
        """
        config = get_env_manager().get_email_config()
        # Mask password for security
        if config.get("smtp_password"):
            config["smtp_password"] = "***"
        return jsonify(config)

    @app.put("/api/email/config")
    def api_put_email_config():
        """Update email configuration.

        Expected JSON body:
            {
                "smtp_server": str,
                "smtp_port": str,
                "smtp_username": str,
                "smtp_password": str,
                "smtp_use_tls": str,
                "from_email": str
            }

        Returns:
            JSON response with update status.
        """
        data = request.get_json(silent=True) or {}

        # Validate required fields
        required_fields = [
            "smtp_server",
            "smtp_username",
            "smtp_password",
            "from_email",
        ]
        missing_fields = [
            field for field in required_fields if not data.get(field, "").strip()
        ]

        if missing_fields:
            return (
                jsonify(
                    {"error": f"Missing required fields: {', '.join(missing_fields)}"}
                ),
                400,
            )

        # Validate email format (basic check)
        from_email = data.get("from_email", "").strip()
        if "@" not in from_email or "." not in from_email:
            return jsonify({"error": "Invalid from_email format"}), 400

        # Validate port number
        try:
            port = int(data.get("smtp_port", 587))
            if not (1 <= port <= 65535):
                raise ValueError()
            data["smtp_port"] = str(port)
        except (ValueError, TypeError):
            return (
                jsonify(
                    {"error": "Invalid smtp_port. Must be a number between 1 and 65535"}
                ),
                400,
            )

        updated = get_env_manager().update_email_config(data)
        return jsonify({"ok": True, "updated": updated})

    @app.post("/api/email/test")
    def api_test_email():
        """Test email configuration by sending a test email.

        Expected JSON body:
            {
                "to_email": str
            }

        Returns:
            JSON response with test result.
        """
        data = request.get_json(silent=True) or {}
        to_email = data.get("to_email", "").strip()

        if not to_email:
            return jsonify({"error": "to_email is required"}), 400

        # Get email configuration
        email_config = get_env_manager().get_email_config()

        # Send test email
        result = send_task_email(
            email_config=email_config,
            to_email=to_email,
            task_name="Email Configuration Test",
            task_result="This is a test email sent from Omni Chat to verify your email configuration is working correctly.",
            task_description="Test email to verify SMTP settings",
            execution_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        if result["success"]:
            return jsonify({"ok": True, "message": result["message"]})
        else:
            return jsonify({"error": result["error"]}), 500

    @app.post("/api/email/send-task-result")
    def api_send_task_result():
        """Send task result via email.

        Expected JSON body:
            {
                "to_email": str,
                "task_name": str,
                "task_result": str,
                "task_description": str (optional),
                "execution_time": str (optional)
            }

        Returns:
            JSON response with send result.
        """
        data = request.get_json(silent=True) or {}

        # Validate required fields
        required_fields = ["to_email", "task_name", "task_result"]
        missing_fields = [field for field in required_fields if not data.get(field)]

        if missing_fields:
            return (
                jsonify(
                    {"error": f"Missing required fields: {', '.join(missing_fields)}"}
                ),
                400,
            )

        # Get email configuration
        email_config = get_env_manager().get_email_config()

        # Send task result email
        result = send_task_email(
            email_config=email_config,
            to_email=data["to_email"],
            task_name=data["task_name"],
            task_result=data["task_result"],
            task_description=data.get("task_description", ""),
            execution_time=data.get("execution_time"),
        )

        if result["success"]:
            return jsonify({"ok": True, "message": result["message"]})
        else:
            return jsonify({"error": result["error"]}), 500

    # Provider/model favorites & defaults ------------------------------------

    @app.get("/api/favorites")
    def api_get_favorites():
        data = providers_manager.load_providers_json()
        return jsonify(
            {"favorites": data.get("favorites", []), "default": data.get("default", {})}
        )

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
                {
                    "name": "temperature",
                    "type": "number",
                    "min": 0,
                    "max": 2,
                    "step": 0.01,
                    "default": 1.0,
                    "label": "Temperature",
                },
                {
                    "name": "top_p",
                    "type": "number",
                    "min": 0,
                    "max": 1,
                    "step": 0.01,
                    "default": 1.0,
                    "label": "Top P",
                },
                {
                    "name": "max_tokens",
                    "type": "integer",
                    "min": 1,
                    "max": 8192,
                    "step": 1,
                    "default": 2048,
                    "label": "Max Tokens",
                },
                {
                    "name": "presence_penalty",
                    "type": "number",
                    "min": -2,
                    "max": 2,
                    "step": 0.01,
                    "default": 0.0,
                    "label": "Presence Penalty",
                },
                {
                    "name": "frequency_penalty",
                    "type": "number",
                    "min": -2,
                    "max": 2,
                    "step": 0.01,
                    "default": 0.0,
                    "label": "Frequency Penalty",
                },
            ]
            # Additional advanced params (exposed only for GPT-5 family to reduce clutter elsewhere)
            if model.lower().startswith("gpt-5"):
                base.extend(
                    [
                        {
                            "name": "seed",
                            "type": "integer",
                            "min": 0,
                            "max": 2147483647,
                            "step": 1,
                            "default": 0,
                            "label": "Seed",
                        },
                        {
                            "name": "stop",
                            "type": "string",
                            "default": "",
                            "label": "Stop Sequences (comma)",
                        },
                        {
                            "name": "response_format",
                            "type": "select",
                            "options": ["text", "json_object"],
                            "default": "text",
                            "label": "Response Format",
                        },
                        {
                            "name": "thinking",
                            "type": "select",
                            "options": ["none", "light", "deep"],
                            "default": "none",
                            "label": "Thinking Mode",
                        },
                        {
                            "name": "thinking_budget_tokens",
                            "type": "integer",
                            "min": 32,
                            "max": 8192,
                            "step": 1,
                            "default": 512,
                            "label": "Thinking Budget",
                        },
                    ]
                )
            if model.lower().startswith("o3"):
                base.append(
                    {
                        "name": "reasoning_effort",
                        "type": "select",
                        "options": ["low", "medium", "high"],
                        "default": "low",
                        "label": "Reasoning Effort",
                    }
                )
            params = base
        elif provider == "gemini":
            params = [
                {
                    "name": "temperature",
                    "type": "number",
                    "min": 0,
                    "max": 2,
                    "step": 0.01,
                    "default": 1.0,
                    "label": "Temperature",
                },
                {
                    "name": "top_p",
                    "type": "number",
                    "min": 0,
                    "max": 1,
                    "step": 0.01,
                    "default": 1.0,
                    "label": "Top P",
                },
                {
                    "name": "top_k",
                    "type": "integer",
                    "min": 1,
                    "max": 100,
                    "step": 1,
                    "default": 40,
                    "label": "Top K",
                },
                {
                    "name": "max_output_tokens",
                    "type": "integer",
                    "min": 16,
                    "max": 8192,
                    "step": 1,
                    "default": 1024,
                    "label": "Max Output Tokens",
                },
                {
                    "name": "web_search",
                    "type": "boolean",
                    "default": False,
                    "label": "Web Search",
                },
            ]
        elif provider == "ollama":
            params = [
                {
                    "name": "temperature",
                    "type": "number",
                    "min": 0,
                    "max": 2,
                    "step": 0.01,
                    "default": 0.8,
                    "label": "Temperature",
                },
                {
                    "name": "top_p",
                    "type": "number",
                    "min": 0,
                    "max": 1,
                    "step": 0.01,
                    "default": 0.9,
                    "label": "Top P",
                },
                {
                    "name": "top_k",
                    "type": "integer",
                    "min": 1,
                    "max": 100,
                    "step": 1,
                    "default": 40,
                    "label": "Top K",
                },
                {
                    "name": "max_tokens",
                    "type": "integer",
                    "min": 1,
                    "max": 8192,
                    "step": 1,
                    "default": 2048,
                    "label": "Max Tokens",
                },
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

    # Task Management API Endpoints
    @app.get("/api/tasks")
    def api_list_tasks():
        """Get all scheduled tasks.

        Returns:
            JSON object with tasks array
        """
        try:
            tasks = list_tasks()
            return jsonify({"tasks": tasks})
        except Exception:  # pragma: no cover
            return jsonify({"error": "failed to load tasks"}), 500

    @app.post("/api/tasks")
    def api_create_task():
        """Create a new scheduled task.

        Expected JSON body:
            {
                "name": str,
                "description": str,
                "date": str (YYYY-MM-DD),
                "time": str (HH:MM),
                "frequency": str,
                "provider": str,
                "model": str,
                "output": str,
                "email": str (optional)
            }
        """
        try:
            data = request.get_json()
            if not data:
                return jsonify({"error": "JSON body required"}), 400

            # Basic validation
            required_fields = [
                "name",
                "description",
                "date",
                "time",
                "frequency",
                "provider",
                "model",
                "output",
            ]
            for field in required_fields:
                if not data.get(field):
                    return jsonify({"error": f"{field} is required"}), 400

            # Validate email if output is email
            if data["output"] == "email" and not data.get("email"):
                return jsonify({"error": "email is required when output is email"}), 400

            # Create task in database
            now = datetime.now(UTC).isoformat()
            task_id = create_task(
                name=data["name"],
                description=data["description"],
                date=data["date"],
                time=data["time"],
                frequency=data["frequency"],
                provider=data["provider"],
                model=data["model"],
                output=data["output"],
                email=data.get("email"),
                now=now,
            )
            commit()

            # Return the created task
            task = get_task(task_id)
            return (
                jsonify(
                    {
                        "id": task_id,
                        "message": "Task created successfully",
                        "task": task,
                    }
                ),
                201,
            )

        except Exception as e:
            return jsonify({"error": f"Failed to create task: {str(e)}"}), 500

    @app.get("/api/tasks/<int:task_id>")
    def api_get_task(task_id: int):
        """Get a specific task by ID.

        Args:
            task_id: The task ID to retrieve
        """
        try:
            task = get_task(task_id)
            if not task:
                return jsonify({"error": "task not found"}), 404
            return jsonify({"task": task})
        except Exception as e:
            return jsonify({"error": f"Failed to get task: {str(e)}"}), 500

    @app.delete("/api/tasks/<int:task_id>")
    def api_delete_task(task_id: int):
        """Delete a scheduled task.

        Args:
            task_id: ID of the task to delete
        """
        try:
            task = get_task(task_id)
            if not task:
                return jsonify({"error": "task not found"}), 404

            db_delete_task(task_id)
            commit()
            return jsonify({"message": f"Task {task_id} deleted successfully"})

        except Exception as e:
            return jsonify({"error": f"Failed to delete task: {str(e)}"}), 500

    @app.put("/api/tasks/<int:task_id>")
    def api_update_task(task_id: int):
        """Update a scheduled task.

        Args:
            task_id: ID of the task to update

        Expected JSON body: Same as create_task
        """
        try:
            task = get_task(task_id)
            if not task:
                return jsonify({"error": "task not found"}), 404

            data = request.get_json()
            if not data:
                return jsonify({"error": "JSON body required"}), 400

            # Basic validation
            required_fields = [
                "name",
                "description",
                "date",
                "time",
                "frequency",
                "provider",
                "model",
                "output",
            ]
            for field in required_fields:
                if not data.get(field):
                    return jsonify({"error": f"{field} is required"}), 400

            # Validate email if output is email
            if data["output"] == "email" and not data.get("email"):
                return jsonify({"error": "email is required when output is email"}), 400

            # Update task in database
            now = datetime.now(UTC).isoformat()
            update_task(
                task_id=task_id,
                name=data["name"],
                description=data["description"],
                date=data["date"],
                time=data["time"],
                frequency=data["frequency"],
                provider=data["provider"],
                model=data["model"],
                output=data["output"],
                email=data.get("email"),
                now=now,
            )
            commit()

            # Return updated task
            updated_task = get_task(task_id)
            return jsonify(
                {
                    "message": f"Task {task_id} updated successfully",
                    "task": updated_task,
                }
            )

        except Exception as e:
            return jsonify({"error": f"Failed to update task: {str(e)}"}), 500

    @app.post("/api/tasks/<int:task_id>/copy")
    def api_copy_task(task_id: int):
        """Create a copy of an existing task.

        Args:
            task_id: ID of the task to copy
        """
        try:
            original_task = get_task(task_id)
            if not original_task:
                return jsonify({"error": "task not found"}), 404

            # Create a copy with modified name
            now = datetime.now(UTC).isoformat()
            new_task_id = create_task(
                name=f"Copy of {original_task['name']}",
                description=original_task["description"],
                date=original_task["date"],
                time=original_task["time"],
                frequency=original_task["frequency"],
                provider=original_task["provider"],
                model=original_task["model"],
                output=original_task["output"],
                email=original_task["email"],
                now=now,
            )
            commit()

            # Return the copied task
            new_task = get_task(new_task_id)
            return (
                jsonify(
                    {
                        "id": new_task_id,
                        "message": "Task copied successfully",
                        "task": new_task,
                    }
                ),
                201,
            )

        except Exception as e:
            return jsonify({"error": f"Failed to copy task: {str(e)}"}), 500

    @app.post("/api/tasks/<int:task_id>/execute")
    def api_execute_task(task_id: int):
        """Execute a task immediately.

        Args:
            task_id: ID of the task to execute
        """
        try:
            # Get the task
            task = get_task(task_id)
            if not task:
                return jsonify({"error": "task not found"}), 404

            # Update task status to running
            execution_time = datetime.now(UTC).isoformat()
            update_task_status(task_id, "running", execution_time)
            commit()

            try:
                # Generate the AI response
                provider = task["provider"]
                model = task["model"]
                prompt = task["description"]

                # Use the existing chat logic to generate response
                chat_reply = generate_reply(provider, model, prompt)

                if chat_reply.error:
                    # Task failed - update status
                    update_task_status(task_id, "failed")
                    commit()
                    return (
                        jsonify(
                            {
                                "error": f"Task execution failed: {chat_reply.error}",
                                "missing_key_for": chat_reply.missing_key_for,
                            }
                        ),
                        500,
                    )

                # Get the response content
                response_content = chat_reply.reply

                # Handle output destination
                if task["output"] == "email":
                    # Send via email
                    if not task["email"]:
                        update_task_status(task_id, "failed")
                        commit()
                        return (
                            jsonify(
                                {"error": "Email address is required for email output"}
                            ),
                            400,
                        )

                    # Get email configuration
                    email_config = get_env_manager().get_email_config()

                    # Send task result email
                    email_result = send_task_email(
                        email_config=email_config,
                        to_email=task["email"],
                        task_name=task["name"],
                        task_result=response_content,
                        task_description=task["description"],
                        execution_time=execution_time,
                    )

                    if not email_result["success"]:
                        update_task_status(task_id, "failed")
                        commit()
                        return (
                            jsonify(
                                {
                                    "error": f"Failed to send email: {email_result['error']}"
                                }
                            ),
                            500,
                        )

                else:
                    # Save to application (create a chat entry)
                    chat_id = create_chat(
                        title=f"Task: {task['name']}", provider=provider, model=model
                    )

                    # Insert user message (the task description)
                    insert_message(
                        chat_id=chat_id, content=prompt, role="user", now=execution_time
                    )

                    # Insert assistant response
                    insert_message(
                        chat_id=chat_id,
                        content=response_content,
                        role="assistant",
                        now=datetime.now(UTC).isoformat(),
                    )

                    commit()

                # Mark task as completed
                update_task_status(task_id, "completed", execution_time)
                commit()

                return jsonify(
                    {
                        "message": "Task executed successfully",
                        "result": response_content,
                        "execution_time": execution_time,
                        "output_method": task["output"],
                    }
                )

            except Exception as execution_error:
                # Update task status to failed
                update_task_status(task_id, "failed")
                commit()
                raise execution_error

        except Exception as e:
            return jsonify({"error": f"Failed to execute task: {str(e)}"}), 500

    return app


# Create the main application instance
app = create_app()

# Initialize Ollama and update providers.json on startup
initialize_ollama_with_app(app)


if __name__ == "__main__":
    # Run the development server
    app.run(debug=True, host="127.0.0.1", port=5000)
