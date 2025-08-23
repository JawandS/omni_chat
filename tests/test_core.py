"""Core functionality tests for Omni Chat.

This module consolidates tests for the most important application functionality:
- Basic chat operations (create, send, retrieve)
- Database operations
- API validation
- Project management (new feature)
"""

import pytest


class TestChatOperations:
    """Test basic chat functionality."""

    def test_create_chat_and_send_message(self, client):
        """Test creating a chat and sending a message."""
        # Create a chat by sending a message
        response = client.post("/api/chat", json={
            "message": "Hello, this is a test",
            "provider": "openai",
            "model": "gpt-4o",
            "title": "Test Chat"
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert "reply" in data
        assert "chat_id" in data
        assert data["title"] == "Test Chat"
        chat_id = data["chat_id"]
        
        # Verify chat exists
        chat_response = client.get(f"/api/chats/{chat_id}")
        assert chat_response.status_code == 200
        chat_data = chat_response.get_json()
        assert chat_data["chat"]["title"] == "Test Chat"
        assert len(chat_data["messages"]) == 2  # user + assistant

    def test_list_chats(self, client):
        """Test listing chats after creating some."""
        # Create a few chats
        for i in range(3):
            client.post("/api/chat", json={
                "message": f"Test message {i}",
                "provider": "openai", 
                "model": "gpt-4o",
                "title": f"Chat {i}"
            })
        
        # List chats
        response = client.get("/api/chats")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["chats"]) == 3

    def test_update_chat_title(self, client):
        """Test updating a chat title."""
        # Create chat
        create_response = client.post("/api/chat", json={
            "message": "Hello",
            "provider": "openai",
            "model": "gpt-4o"
        })
        chat_id = create_response.get_json()["chat_id"]
        
        # Update title
        update_response = client.patch(f"/api/chats/{chat_id}", json={
            "title": "Updated Title"
        })
        assert update_response.status_code == 200
        
        # Verify update
        chat_response = client.get(f"/api/chats/{chat_id}")
        assert chat_response.get_json()["chat"]["title"] == "Updated Title"

    def test_delete_chat(self, client):
        """Test deleting a chat."""
        # Create chat
        create_response = client.post("/api/chat", json={
            "message": "Hello",
            "provider": "openai",
            "model": "gpt-4o"
        })
        chat_id = create_response.get_json()["chat_id"]
        
        # Delete chat
        delete_response = client.delete(f"/api/chats/{chat_id}")
        assert delete_response.status_code == 200
        
        # Verify deletion
        chat_response = client.get(f"/api/chats/{chat_id}")
        assert chat_response.status_code == 404


class TestProjectOperations:
    """Test project management functionality."""

    def test_create_project(self, client):
        """Test creating a project."""
        response = client.post("/api/projects", json={"name": "Test Project"})
        assert response.status_code == 200
        data = response.get_json()
        assert data["project"]["name"] == "Test Project"
        assert "id" in data["project"]

    def test_list_projects(self, client):
        """Test listing projects."""
        # Create a few projects
        for i in range(3):
            client.post("/api/projects", json={"name": f"Project {i}"})
        
        response = client.get("/api/projects")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["projects"]) == 3

    def test_delete_project(self, client):
        """Test deleting a project."""
        # Create project
        create_response = client.post("/api/projects", json={"name": "Test Project"})
        project_id = create_response.get_json()["project"]["id"]
        
        # Delete project
        delete_response = client.delete(f"/api/projects/{project_id}")
        assert delete_response.status_code == 200
        
        # Verify deletion
        projects_response = client.get("/api/projects")
        projects = projects_response.get_json()["projects"]
        assert not any(p["id"] == project_id for p in projects)

    def test_add_chat_to_project(self, client):
        """Test adding a chat to a project."""
        # Create project
        project_response = client.post("/api/projects", json={"name": "Test Project"})
        project_id = project_response.get_json()["project"]["id"]
        
        # Create chat
        chat_response = client.post("/api/chat", json={
            "message": "Hello",
            "provider": "openai",
            "model": "gpt-4o"
        })
        chat_id = chat_response.get_json()["chat_id"]
        
        # Add chat to project
        add_response = client.post(f"/api/chats/{chat_id}/project", json={
            "project_id": project_id
        })
        assert add_response.status_code == 200
        
        # Verify chat is in project
        project_chats_response = client.get(f"/api/chats/by-project?project_id={project_id}")
        chats = project_chats_response.get_json()["chats"]
        assert len(chats) == 1
        assert chats[0]["id"] == chat_id


class TestAPIValidation:
    """Test API request validation."""

    def test_missing_required_fields(self, client):
        """Test validation of required fields."""
        # Missing message
        response = client.post("/api/chat", json={
            "provider": "openai",
            "model": "gpt-4o"
        })
        assert response.status_code == 400
        assert "message is required" in response.get_json()["error"]
        
        # Missing provider
        response = client.post("/api/chat", json={
            "message": "Hello",
            "model": "gpt-4o"
        })
        assert response.status_code == 400
        assert "provider is required" in response.get_json()["error"]
        
        # Missing model
        response = client.post("/api/chat", json={
            "message": "Hello",
            "provider": "openai"
        })
        assert response.status_code == 400
        assert "model is required" in response.get_json()["error"]

    def test_empty_message(self, client):
        """Test validation of empty messages."""
        response = client.post("/api/chat", json={
            "message": "   ",  # whitespace only
            "provider": "openai",
            "model": "gpt-4o"
        })
        assert response.status_code == 400
        assert "message is required" in response.get_json()["error"]

    def test_invalid_json(self, client):
        """Test handling of invalid JSON."""
        response = client.post("/api/chat", 
                              data="invalid json",
                              content_type="application/json")
        assert response.status_code == 400


class TestProviderConfiguration:
    """Test provider and model configuration."""

    def test_get_providers_config(self, client):
        """Test getting provider configuration."""
        response = client.get("/api/providers-config")
        assert response.status_code == 200
        data = response.get_json()
        assert "providers" in data
        assert "favorites" in data
        assert "default" in data
        
        # Verify OpenAI provider exists (from template)
        providers = data["providers"]
        openai_provider = next((p for p in providers if p["id"] == "openai"), None)
        assert openai_provider is not None
        assert "gpt-4o" in openai_provider["models"]

    def test_favorites_operations(self, client):
        """Test adding and removing favorites."""
        # Add favorite
        add_response = client.post("/api/favorites", json={
            "provider": "openai",
            "model": "gpt-4o"
        })
        assert add_response.status_code == 200
        assert "openai:gpt-4o" in add_response.get_json()["favorites"]
        
        # Remove favorite
        remove_response = client.delete("/api/favorites?provider=openai&model=gpt-4o")
        assert remove_response.status_code == 200
        assert "openai:gpt-4o" not in remove_response.get_json()["favorites"]

    def test_model_config_endpoint(self, client):
        """Test getting model configuration parameters."""
        response = client.get("/api/model-config?provider=openai&model=gpt-4o")
        assert response.status_code == 200
        data = response.get_json()
        assert data["provider"] == "openai"
        assert data["model"] == "gpt-4o"
        assert "params" in data
        
        # Verify some expected parameters
        param_names = [p["name"] for p in data["params"]]
        assert "temperature" in param_names
        assert "max_tokens" in param_names


class TestAPIKeys:
    """Test API key management."""

    def test_api_key_operations(self, client):
        """Test setting and getting API keys."""
        # Set keys
        set_response = client.put("/api/keys", json={
            "openai": "test-key-123",
            "gemini": "gemini-test-key"
        })
        assert set_response.status_code == 200

        # Get keys (should be masked)
        get_response = client.get("/api/keys")
        assert get_response.status_code == 200
        data = get_response.get_json()
        assert data["openai"].startswith("test-key")
        assert data["gemini"].startswith("gemini-test")

        # Delete a key
        delete_response = client.delete("/api/keys/openai")
        assert delete_response.status_code == 200

        # Verify key was removed
        get_response = client.get("/api/keys")
        data = get_response.get_json()
        assert data["openai"] == ""
class TestBlacklist:
    """Test blacklist functionality."""

    def test_blacklist_operations(self, client):
        """Test adding and removing blacklist words."""
        # Add word
        add_response = client.post("/api/blacklist", json={"word": "badword"})
        assert add_response.status_code == 200
        assert "badword" in add_response.get_json()["blacklist"]
        
        # Remove word
        remove_response = client.delete("/api/blacklist?word=badword")
        assert remove_response.status_code == 200
        assert "badword" not in remove_response.get_json()["blacklist"]
