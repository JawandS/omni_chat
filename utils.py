"""
Shared utility functions for the Omni Chat application.

This module provides common utilities and helper functions used throughout the
application. It handles configuration management, validation, and reusable
business logic that doesn't belong to specific modules.

Key Components:
    - Request validation functions for API endpoints
    - Environment and configuration management classes
    - Provider configuration handling
    - Chat management utilities
    - Timestamp and formatting helpers

Classes:
    - EnvironmentManager: Handles .env file operations and API key management
    - ProvidersConfigManager: Manages provider configuration and model settings

Functions:
    - validate_chat_request(): Validates incoming chat API requests
    - generate_chat_title(): Creates meaningful chat titles from messages
    - create_or_update_chat(): Handles chat creation and updates
    - get_timestamp(): Provides consistent UTC timestamp formatting

Architecture:
    - Centralized configuration management
    - Type-safe validation with clear error messages
    - Environment isolation for testing
    - Provider-agnostic configuration handling

Usage:
    >>> env_mgr = EnvironmentManager("/path/to/.env")
    >>> keys = env_mgr.get_api_keys()
    >>> message, provider, model = validate_chat_request(request_data)

Security:
    - Safe environment variable handling
    - Input validation with detailed error messages
    - Secure API key storage and retrieval
    - Test isolation with temporary configuration files
"""

import json
import os
from typing import Optional, Dict, Any, Tuple

from dotenv import load_dotenv, set_key, unset_key, dotenv_values


def validate_chat_request(data: dict) -> tuple[str, str, str]:
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


def generate_chat_title(message: str, existing_title: str = "") -> str:
    """Generate a default title for a chat based on the message.

    Args:
        message: The chat message to generate title from.
        existing_title: Existing title if any.

    Returns:
        Generated title string.
    """
    if existing_title.strip():
        return existing_title.strip()

    if not message:
        return "New chat"

    return (message[:48] + "…") if len(message) > 49 else message


class EnvironmentManager:
    """Manages environment variables and .env file operations."""

    def __init__(self, env_path: str):
        self.env_path = env_path

    def get_env_path(self) -> str:
        """Get the path to the .env file for environment variable storage."""
        return self.env_path

    def load_env_into_process(self) -> None:
        """Ensure process environment reflects file updates."""
        load_dotenv(self.env_path, override=True)

    def get_api_keys(self) -> Dict[str, str]:
        """Get current API keys for all providers.

        Returns:
            Dictionary with provider names as keys and API keys as values.
        """
        # Prefer file values; fall back to current process env
        values = dotenv_values(self.env_path)
        openai_key = values.get("OPENAI_API_KEY") if values else None
        gemini_key = values.get("GEMINI_API_KEY") if values else None

        # If not in file, try process env
        openai_key = openai_key or os.getenv("OPENAI_API_KEY", "")
        gemini_key = gemini_key or os.getenv("GEMINI_API_KEY", "")

        return {
            "openai": openai_key or "",
            "gemini": gemini_key or "",
        }

    def update_api_keys(self, keys_data: Dict[str, Any]) -> Dict[str, Optional[str]]:
        """Set or update API keys for providers.

        Args:
            keys_data: Dictionary with provider keys to update.

        Returns:
            Dictionary of updated keys.
        """
        os.makedirs(os.path.dirname(self.env_path), exist_ok=True)

        updated: Dict[str, Optional[str]] = {}
        key_mapping = [("OPENAI_API_KEY", "openai"), ("GEMINI_API_KEY", "gemini")]

        for env_key, body_key in key_mapping:
            if body_key in keys_data:
                value = keys_data.get(body_key)
                if value is None or str(value).strip() == "":
                    # Remove the key
                    try:
                        unset_key(self.env_path, env_key)
                    except Exception:
                        pass
                    os.environ.pop(env_key, None)
                    updated[body_key] = None
                else:
                    # Set the key
                    set_key(self.env_path, env_key, str(value), quote_mode="never")
                    os.environ[env_key] = str(value)
                    updated[body_key] = str(value)

        self.load_env_into_process()
        return updated

    def delete_api_key(self, provider: str) -> bool:
        """Delete API key for a specific provider.

        Args:
            provider: Provider name ('openai' or 'gemini').

        Returns:
            True if successful, False if provider is unknown.
        """
        key_mapping = {"openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY"}
        env_key = key_mapping.get(provider.lower())

        if not env_key:
            return False

        try:
            unset_key(self.env_path, env_key)
        except Exception:
            pass

        os.environ.pop(env_key, None)
        self.load_env_into_process()
        return True

    def get_email_config(self) -> Dict[str, str]:
        """Get current email configuration.

        Returns:
            Dictionary with email configuration values.
        """
        values = dotenv_values(self.env_path)

        return {
            "smtp_server": values.get("SMTP_SERVER") or os.getenv("SMTP_SERVER") or "",
            "smtp_port": values.get("SMTP_PORT") or os.getenv("SMTP_PORT") or "587",
            "smtp_username": values.get("SMTP_USERNAME")
            or os.getenv("SMTP_USERNAME")
            or "",
            "smtp_password": values.get("SMTP_PASSWORD")
            or os.getenv("SMTP_PASSWORD")
            or "",
            "smtp_use_tls": values.get("SMTP_USE_TLS")
            or os.getenv("SMTP_USE_TLS")
            or "true",
            "from_email": values.get("FROM_EMAIL") or os.getenv("FROM_EMAIL") or "",
        }

    def update_email_config(
        self, email_data: Dict[str, Any]
    ) -> Dict[str, Optional[str]]:
        """Set or update email configuration.

        Args:
            email_data: Dictionary with email config to update.

        Returns:
            Dictionary of updated email config.
        """
        os.makedirs(os.path.dirname(self.env_path), exist_ok=True)

        updated: Dict[str, Optional[str]] = {}
        key_mapping = [
            ("SMTP_SERVER", "smtp_server"),
            ("SMTP_PORT", "smtp_port"),
            ("SMTP_USERNAME", "smtp_username"),
            ("SMTP_PASSWORD", "smtp_password"),
            ("SMTP_USE_TLS", "smtp_use_tls"),
            ("FROM_EMAIL", "from_email"),
        ]

        for env_key, body_key in key_mapping:
            if body_key in email_data:
                value = email_data.get(body_key)
                if value is None or str(value).strip() == "":
                    # Remove the key
                    try:
                        unset_key(self.env_path, env_key)
                    except Exception:
                        pass
                    os.environ.pop(env_key, None)
                    updated[body_key] = None
                else:
                    # Set the key
                    set_key(self.env_path, env_key, str(value), quote_mode="never")
                    os.environ[env_key] = str(value)
                    updated[body_key] = str(value)

        self.load_env_into_process()
        return updated


class ProvidersConfigManager:
    """Manages provider configuration JSON file operations."""

    def __init__(self, providers_json_path: str):
        self.providers_json_path = providers_json_path

    def load_providers_json(self) -> dict:
        """Load providers configuration from JSON file.

        Returns:
            Dictionary containing providers configuration.

        Raises:
            FileNotFoundError: If neither providers.json nor template exists.
            Exception: If there's an error loading the file.
        """
        try:
            with open(self.providers_json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            # If providers.json doesn't exist, try to copy from providers_template.json
            template_path = os.path.join(
                os.path.dirname(self.providers_json_path), "providers_template.json"
            )
            try:
                with open(template_path, "r", encoding="utf-8") as f:
                    template_data = json.load(f)
                # Copy template to providers.json
                self.write_providers_json(template_data)
                return template_data
            except FileNotFoundError:
                raise FileNotFoundError(
                    f"Required template file not found: {template_path}. "
                    "Cannot initialize providers configuration."
                )
            except Exception as e:
                raise Exception(f"Error loading template file {template_path}: {e}")
        except Exception as e:
            raise Exception(f"Error loading providers.json: {e}")

    def write_providers_json(self, data: dict) -> None:
        """Write providers configuration to JSON file.

        Args:
            data: Configuration data to write.
        """
        os.makedirs(os.path.dirname(self.providers_json_path), exist_ok=True)
        tmp_path = self.providers_json_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, self.providers_json_path)

    def validate_provider_model(self, provider: str, model: str) -> bool:
        """Validate that a provider and model combination is valid.

        Args:
            provider: Provider ID to validate.
            model: Model name to validate.

        Returns:
            True if valid, False otherwise.
        """
        try:
            data = self.load_providers_json()
            for p in data.get("providers", []):
                if p.get("id") == provider and model in (p.get("models") or []):
                    return True
            return False
        except Exception:
            return False


def escape_html(text: str) -> str:
    """Escape HTML special characters in text.

    Args:
        text: Text to escape.

    Returns:
        HTML-escaped text.
    """
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def truncate_text(text: str, max_length: int = 50, suffix: str = "…") -> str:
    """Truncate text to a maximum length with optional suffix.

    Args:
        text: Text to truncate.
        max_length: Maximum length before truncation.
        suffix: Suffix to add when truncating.

    Returns:
        Truncated text.
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def format_timestamp(timestamp: str) -> str:
    """Format ISO timestamp for display.

    Args:
        timestamp: ISO format timestamp string.

    Returns:
        Formatted timestamp string.
    """
    try:
        from datetime import datetime

        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return timestamp


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename for safe filesystem usage.

    Args:
        filename: Original filename.

    Returns:
        Sanitized filename.
    """
    import re

    # Remove or replace unsafe characters
    filename = re.sub(r'[<>:"/\\|?*]', "_", filename)
    # Remove control characters
    filename = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", filename)
    # Limit length
    return filename[:255]


# Database and chat management utilities
def get_timestamp(now: Optional[str] = None) -> str:
    """Get current timestamp or provided timestamp.

    Args:
        now: Optional timestamp string. If None, current UTC time is used.

    Returns:
        ISO formatted timestamp string.
    """
    from datetime import datetime, UTC

    return now or datetime.now(UTC).isoformat()


def get_api_key(provider: str) -> str:
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


def create_or_update_chat(
    chat_id: Optional[int], title: str, provider: str, model: str, now: str, project_id: Optional[int] = None
) -> int:
    """Create a new chat or update existing chat metadata.

    Args:
        chat_id: Optional existing chat ID.
        title: Chat title.
        provider: AI provider name.
        model: AI model name.
        now: Current timestamp.
        project_id: Optional project ID to assign the chat to (only used for new chats).

    Returns:
        Chat ID (new or existing).
    """
    from database import create_chat, update_chat_meta

    if not chat_id:
        chat_id = create_chat(title, provider, model, now, project_id)
    else:
        update_chat_meta(chat_id, provider, model, now)
    return chat_id


# Ollama utilities
def is_ollama_available() -> bool:
    """Check if Ollama is installed and available on the system.

    Returns:
        True if ollama command is available, False otherwise.
    """
    import subprocess

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
    import logging

    logger = logging.getLogger(__name__)

    try:
        import requests
    except ImportError:
        logger.warning("[OLLAMA] requests library not available for server check")
        return False

    try:
        logger.info(
            "[OLLAMA] Checking if server is running at http://localhost:11434/api/tags"
        )
        response = requests.get("http://localhost:11434/api/tags", timeout=15)

        if response.status_code == 200:
            logger.info("[OLLAMA] Server is running and responding")
            return True
        else:
            logger.warning(
                f"[OLLAMA] Server responded with status {response.status_code}"
            )
            return False

    except requests.RequestException as e:
        logger.warning(f"[OLLAMA] Server check failed: {type(e).__name__}: {e}")
        return False


def start_ollama_server() -> bool:
    """Start Ollama server if it's not running.

    Returns:
        True if server was started or already running, False on error.
    """
    import subprocess
    import time

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


def get_ollama_models() -> list:
    """Get list of available Ollama models.

    Returns:
        List of model names, empty if Ollama is not available.
    """
    try:
        import requests
    except ImportError:
        return []

    if not is_ollama_server_running():
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


def initialize_ollama_with_app(app_instance):
    """Initialize Ollama server and update providers.json at startup."""
    import logging

    try:
        # Create a providers manager for this context
        providers_json_path = os.environ.get(
            "PROVIDERS_JSON_PATH",
            os.path.join(app_instance.root_path, "static", "providers.json"),
        )
        providers_mgr = ProvidersConfigManager(providers_json_path)

        # Load current providers data
        data = providers_mgr.load_providers_json()
        providers = data.get("providers", [])

        # Remove existing Ollama provider if present
        providers = [p for p in providers if p.get("id") != "ollama"]

        # Check if Ollama is available and get models
        if is_ollama_available():
            # Try to start Ollama server if not running
            if start_ollama_server():
                # Get available models
                models = get_ollama_models()
                if models:
                    # Add Ollama provider with current models
                    ollama_provider = {
                        "id": "ollama",
                        "name": "Ollama (Local)",
                        "models": models,
                    }
                    providers.append(ollama_provider)
            # If startup fails, just skip Ollama - not an error worth logging
        # If Ollama not available, just skip it - this is normal

        # Update providers data and save
        data["providers"] = providers
        providers_mgr.write_providers_json(data)

    except Exception as e:
        # Only log errors during Ollama initialization
        logging.getLogger(__name__).error(f"Error initializing Ollama: {e}")
