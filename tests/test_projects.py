"""Tests for project management functionality."""

import pytest


def test_create_project(client):
    """Test creating a new project."""
    resp = client.post(
        "/api/projects",
        json={
            "name": "Test Project",
            "description": "A test project",
            "system_prompt": "You are a helpful assistant.",
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert "project_id" in data
    assert data["name"] == "Test Project"


def test_create_project_name_required(client):
    """Test that project name is required."""
    resp = client.post("/api/projects", json={})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "name is required"


def test_create_project_empty_name(client):
    """Test that empty project name is rejected."""
    resp = client.post("/api/projects", json={"name": "   "})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "name is required"


def test_list_projects(client):
    """Test listing projects."""
    # Create a project first
    resp = client.post("/api/projects", json={"name": "Test Project"})
    assert resp.status_code == 200

    # List projects
    resp = client.get("/api/projects")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "projects" in data
    assert len(data["projects"]) == 1
    assert data["projects"][0]["name"] == "Test Project"


def test_get_project(client):
    """Test getting a specific project."""
    # Create a project
    resp = client.post(
        "/api/projects",
        json={
            "name": "Test Project",
            "description": "A test project",
            "system_prompt": "You are helpful.",
        },
    )
    project_id = resp.get_json()["project_id"]

    # Get the project
    resp = client.get(f"/api/projects/{project_id}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["project"]["id"] == project_id
    assert data["project"]["name"] == "Test Project"
    assert data["project"]["description"] == "A test project"
    assert data["project"]["system_prompt"] == "You are helpful."
    assert "files" in data
    assert "chats" in data


def test_get_nonexistent_project(client):
    """Test getting a project that doesn't exist."""
    resp = client.get("/api/projects/999")
    assert resp.status_code == 404
    data = resp.get_json()
    assert data["error"] == "not found"


def test_update_project(client):
    """Test updating a project."""
    # Create a project
    resp = client.post("/api/projects", json={"name": "Original Name"})
    project_id = resp.get_json()["project_id"]

    # Update the project
    resp = client.patch(
        f"/api/projects/{project_id}",
        json={
            "name": "Updated Name",
            "description": "Updated description",
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True

    # Verify the update
    resp = client.get(f"/api/projects/{project_id}")
    data = resp.get_json()
    assert data["project"]["name"] == "Updated Name"
    assert data["project"]["description"] == "Updated description"


def test_update_project_empty_name(client):
    """Test that updating with empty name is rejected."""
    # Create a project
    resp = client.post("/api/projects", json={"name": "Original Name"})
    project_id = resp.get_json()["project_id"]

    # Try to update with empty name
    resp = client.patch(f"/api/projects/{project_id}", json={"name": "   "})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "name cannot be empty"


def test_update_nonexistent_project(client):
    """Test updating a project that doesn't exist."""
    resp = client.patch("/api/projects/999", json={"name": "New Name"})
    assert resp.status_code == 404
    data = resp.get_json()
    assert data["error"] == "not found"


def test_delete_project(client):
    """Test deleting a project."""
    # Create a project
    resp = client.post("/api/projects", json={"name": "Test Project"})
    project_id = resp.get_json()["project_id"]

    # Delete the project
    resp = client.delete(f"/api/projects/{project_id}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True

    # Verify it's gone
    resp = client.get(f"/api/projects/{project_id}")
    assert resp.status_code == 404


def test_delete_nonexistent_project(client):
    """Test deleting a project that doesn't exist."""
    resp = client.delete("/api/projects/999")
    assert resp.status_code == 404
    data = resp.get_json()
    assert data["error"] == "not found"


def test_create_project_file(client):
    """Test creating a file in a project."""
    # Create a project
    resp = client.post("/api/projects", json={"name": "Test Project"})
    project_id = resp.get_json()["project_id"]

    # Create a file
    resp = client.post(
        f"/api/projects/{project_id}/files",
        json={"filename": "test.txt", "content": "Hello, world!"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert "file_id" in data
    assert data["filename"] == "test.txt"


def test_create_file_in_nonexistent_project(client):
    """Test creating a file in a project that doesn't exist."""
    resp = client.post(
        "/api/projects/999/files",
        json={"filename": "test.txt", "content": "Hello, world!"},
    )
    assert resp.status_code == 404
    data = resp.get_json()
    assert data["error"] == "project not found"


def test_create_file_missing_filename(client):
    """Test that filename is required when creating a file."""
    # Create a project
    resp = client.post("/api/projects", json={"name": "Test Project"})
    project_id = resp.get_json()["project_id"]

    # Try to create file without filename
    resp = client.post(
        f"/api/projects/{project_id}/files", json={"content": "Hello, world!"}
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "filename is required"


def test_project_files_in_project_details(client):
    """Test that project files are included in project details."""
    # Create a project
    resp = client.post("/api/projects", json={"name": "Test Project"})
    project_id = resp.get_json()["project_id"]

    # Create a file
    resp = client.post(
        f"/api/projects/{project_id}/files",
        json={"filename": "test.txt", "content": "Hello, world!"},
    )
    file_id = resp.get_json()["file_id"]

    # Get project details
    resp = client.get(f"/api/projects/{project_id}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["files"]) == 1
    assert data["files"][0]["id"] == file_id
    assert data["files"][0]["filename"] == "test.txt"
    assert data["files"][0]["content"] == "Hello, world!"


def test_update_project_file(client):
    """Test updating a project file."""
    # Create a project
    resp = client.post("/api/projects", json={"name": "Test Project"})
    project_id = resp.get_json()["project_id"]

    # Create a file
    resp = client.post(
        f"/api/projects/{project_id}/files",
        json={"filename": "test.txt", "content": "Original content"},
    )
    file_id = resp.get_json()["file_id"]

    # Update the file
    resp = client.patch(
        f"/api/projects/{project_id}/files/{file_id}",
        json={"filename": "updated.txt", "content": "Updated content"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True

    # Verify the update
    resp = client.get(f"/api/projects/{project_id}")
    data = resp.get_json()
    file = data["files"][0]
    assert file["filename"] == "updated.txt"
    assert file["content"] == "Updated content"


def test_delete_project_file(client):
    """Test deleting a project file."""
    # Create a project
    resp = client.post("/api/projects", json={"name": "Test Project"})
    project_id = resp.get_json()["project_id"]

    # Create a file
    resp = client.post(
        f"/api/projects/{project_id}/files",
        json={"filename": "test.txt", "content": "Hello, world!"},
    )
    file_id = resp.get_json()["file_id"]

    # Delete the file
    resp = client.delete(f"/api/projects/{project_id}/files/{file_id}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True

    # Verify it's gone
    resp = client.get(f"/api/projects/{project_id}")
    data = resp.get_json()
    assert len(data["files"]) == 0


def test_chat_project_association(client):
    """Test associating a chat with a project."""
    # Create a project
    resp = client.post("/api/projects", json={"name": "Test Project"})
    project_id = resp.get_json()["project_id"]

    # Create a chat associated with the project
    resp = client.post(
        "/api/chat",
        json={
            "message": "Hello",
            "history": [],
            "provider": "openai",
            "model": "gpt-4o-mini",
            "title": "Test Chat",
            "project_id": project_id,
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()
    chat_id = data["chat_id"]

    # Verify the chat is associated with the project
    resp = client.get(f"/api/chats/{chat_id}")
    chat_data = resp.get_json()
    assert chat_data["chat"]["project_id"] == project_id

    # Verify the chat appears in project details
    resp = client.get(f"/api/projects/{project_id}")
    project_data = resp.get_json()
    assert len(project_data["chats"]) == 1
    assert project_data["chats"][0]["id"] == chat_id


def test_delete_project_preserves_chats(client):
    """Test that deleting a project preserves associated chats but sets project_id to null."""
    # Create a project
    resp = client.post("/api/projects", json={"name": "Test Project"})
    project_id = resp.get_json()["project_id"]

    # Create a chat associated with the project
    resp = client.post(
        "/api/chat",
        json={
            "message": "Hello",
            "history": [],
            "provider": "openai",
            "model": "gpt-4o-mini",
            "title": "Test Chat",
            "project_id": project_id,
        },
    )
    chat_id = resp.get_json()["chat_id"]

    # Delete the project
    resp = client.delete(f"/api/projects/{project_id}")
    assert resp.status_code == 200

    # Verify the chat still exists but has no project_id
    resp = client.get(f"/api/chats/{chat_id}")
    assert resp.status_code == 200
    chat_data = resp.get_json()
    assert chat_data["chat"]["project_id"] is None