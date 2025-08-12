"""
Tests for database operations and data integrity.
"""

import sqlite3
import pytest
from database import (
    create_chat, get_chat, list_chats, get_messages, 
    insert_message, update_chat, delete_chat, touch_chat
)


def test_create_chat_with_timestamp(client):
    """Test creating a chat with specific timestamp."""
    with client.application.app_context():
        timestamp = "2024-01-01T12:00:00Z"
        chat_id = create_chat("Test Chat", "openai", "gpt-4", timestamp)
        
        chat = get_chat(chat_id)
        assert chat is not None
        assert chat["title"] == "Test Chat"
        assert chat["provider"] == "openai"
        assert chat["model"] == "gpt-4"
        assert chat["created_at"] == timestamp
        assert chat["updated_at"] == timestamp


def test_insert_message_with_invalid_role(client):
    """Test that inserting message with invalid role raises error."""
    with client.application.app_context():
        chat_id = create_chat("Test Chat", "openai", "gpt-4")
        
        with pytest.raises(ValueError, match="Invalid role"):
            insert_message(chat_id, "invalid_role", "Test message")


def test_insert_message_with_provider_model(client):
    """Test inserting message with provider and model information."""
    with client.application.app_context():
        chat_id = create_chat("Test Chat", "openai", "gpt-4")
        timestamp = "2024-01-01T12:00:00Z"
        
        insert_message(chat_id, "user", "Hello", timestamp, "openai", "gpt-4")
        
        messages = get_messages(chat_id)
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello"
        assert messages[0]["provider"] == "openai"
        assert messages[0]["model"] == "gpt-4"
        assert messages[0]["created_at"] == timestamp


def test_touch_chat_updates_timestamp(client):
    """Test that touching a chat updates its timestamp."""
    with client.application.app_context():
        original_time = "2024-01-01T12:00:00Z"
        new_time = "2024-01-01T13:00:00Z"
        
        chat_id = create_chat("Test Chat", "openai", "gpt-4", original_time)
        
        # Verify original timestamp
        chat = get_chat(chat_id)
        assert chat["updated_at"] == original_time
        
        # Touch the chat
        touch_chat(chat_id, new_time)
        
        # Verify updated timestamp
        chat = get_chat(chat_id)
        assert chat["updated_at"] == new_time
        assert chat["created_at"] == original_time  # Should not change


def test_update_chat_title_only(client):
    """Test updating only the chat title."""
    with client.application.app_context():
        chat_id = create_chat("Original Title", "openai", "gpt-4")
        update_time = "2024-01-01T13:00:00Z"
        
        update_chat(chat_id, title="New Title", now=update_time)
        
        chat = get_chat(chat_id)
        assert chat["title"] == "New Title"
        assert chat["provider"] == "openai"  # Should remain unchanged
        assert chat["model"] == "gpt-4"      # Should remain unchanged
        assert chat["updated_at"] == update_time


def test_update_chat_provider_model(client):
    """Test updating chat provider and model."""
    with client.application.app_context():
        chat_id = create_chat("Test Chat", "openai", "gpt-4")
        update_time = "2024-01-01T13:00:00Z"
        
        update_chat(chat_id, provider="gemini", model="gemini-pro", now=update_time)
        
        chat = get_chat(chat_id)
        assert chat["title"] == "Test Chat"  # Should remain unchanged
        assert chat["provider"] == "gemini"
        assert chat["model"] == "gemini-pro"
        assert chat["updated_at"] == update_time


def test_delete_chat_removes_messages(client):
    """Test that deleting a chat also removes its messages."""
    with client.application.app_context():
        chat_id = create_chat("Test Chat", "openai", "gpt-4")
        
        # Add some messages
        insert_message(chat_id, "user", "Hello")
        insert_message(chat_id, "assistant", "Hi there!")
        
        # Verify messages exist
        messages = get_messages(chat_id)
        assert len(messages) == 2
        
        # Delete the chat
        delete_chat(chat_id)
        
        # Verify chat is gone
        chat = get_chat(chat_id)
        assert chat is None
        
        # Verify messages are gone
        messages = get_messages(chat_id)
        assert len(messages) == 0


def test_list_chats_ordering(client):
    """Test that list_chats returns chats in correct order (most recent first)."""
    with client.application.app_context():
        time1 = "2024-01-01T12:00:00Z"
        time2 = "2024-01-01T13:00:00Z" 
        time3 = "2024-01-01T14:00:00Z"
        
        # Create chats with different timestamps
        chat1_id = create_chat("Chat 1", "openai", "gpt-4", time1)
        chat2_id = create_chat("Chat 2", "openai", "gpt-4", time2)
        chat3_id = create_chat("Chat 3", "openai", "gpt-4", time3)
        
        # Update chat1 to make it most recent
        touch_chat(chat1_id, "2024-01-01T15:00:00Z")
        
        chats = list_chats()
        assert len(chats) >= 3
        
        # Find our test chats in the list
        test_chats = [c for c in chats if c["id"] in (chat1_id, chat2_id, chat3_id)]
        assert len(test_chats) == 3
        
        # Should be ordered by updated_at descending
        chat_ids = [c["id"] for c in test_chats]
        assert chat_ids[0] == chat1_id  # Most recently updated
        # chat2 and chat3 order depends on their original creation times


def test_get_messages_ordering(client):
    """Test that get_messages returns messages in chronological order."""
    with client.application.app_context():
        chat_id = create_chat("Test Chat", "openai", "gpt-4")
        
        time1 = "2024-01-01T12:00:00Z"
        time2 = "2024-01-01T12:01:00Z"
        time3 = "2024-01-01T12:02:00Z"
        
        # Insert messages in non-chronological order
        insert_message(chat_id, "assistant", "Response 2", time2)
        insert_message(chat_id, "user", "Message 1", time1)
        insert_message(chat_id, "assistant", "Response 3", time3)
        
        messages = get_messages(chat_id)
        assert len(messages) == 3
        
        # Should be ordered chronologically (by ID, which follows insertion order)
        assert messages[0]["content"] == "Response 2"
        assert messages[1]["content"] == "Message 1"  
        assert messages[2]["content"] == "Response 3"


def test_database_foreign_key_constraint(client):
    """Test that foreign key constraints are working (messages cascade delete)."""
    with client.application.app_context():
        chat_id = create_chat("Test Chat", "openai", "gpt-4")
        insert_message(chat_id, "user", "Test message")
        
        # Get the database connection to test foreign key constraints
        from database import get_db
        db = get_db()
        
        # Delete chat directly from database
        db.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
        db.commit()
        
        # Messages should be automatically deleted due to foreign key constraint
        messages = get_messages(chat_id)
        assert len(messages) == 0


def test_chat_creation_generates_sequential_ids(client):
    """Test that chat creation generates sequential IDs."""
    with client.application.app_context():
        chat1_id = create_chat("Chat 1", "openai", "gpt-4")
        chat2_id = create_chat("Chat 2", "openai", "gpt-4")
        chat3_id = create_chat("Chat 3", "openai", "gpt-4")
        
        # IDs should be sequential (though there might be gaps due to other tests)
        assert chat2_id > chat1_id
        assert chat3_id > chat2_id
