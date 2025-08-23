"""Shared utility functions for the Omni Chat application."""

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
            "openai": openai_key,
            "gemini": gemini_key,
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
    return text[:max_length - len(suffix)] + suffix


def format_timestamp(timestamp: str) -> str:
    """Format ISO timestamp for display.
    
    Args:
        timestamp: ISO format timestamp string.
        
    Returns:
        Formatted timestamp string.
    """
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M')
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
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Remove control characters
    filename = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', filename)
    # Limit length
    return filename[:255]
