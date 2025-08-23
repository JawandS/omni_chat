"""Tests for blacklist management endpoints."""


def test_get_initial_blacklist(client):
    """Test getting initial empty blacklist."""
    r = client.get("/api/blacklist")
    assert r.status_code == 200
    data = r.get_json()
    assert "blacklist" in data


def test_add_blacklist_word(client):
    """Test adding a word to blacklist."""
    r = client.post("/api/blacklist", json={"word": "badword"})
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True
    assert "badword" in data["blacklist"]


def test_add_blacklist_word_case_insensitive(client):
    """Test adding a word with different case."""
    # Add in uppercase
    r1 = client.post("/api/blacklist", json={"word": "BADWORD"})
    assert r1.status_code == 200
    
    # Should be stored as lowercase
    data = r1.get_json()
    assert "badword" in data["blacklist"]
    assert "BADWORD" not in data["blacklist"]


def test_add_blacklist_word_duplicate(client):
    """Test adding the same word twice (should be idempotent)."""
    # Add word first time
    r1 = client.post("/api/blacklist", json={"word": "duplicate"})
    assert r1.status_code == 200
    first_count = len(r1.get_json()["blacklist"])
    
    # Add same word again
    r2 = client.post("/api/blacklist", json={"word": "duplicate"})
    assert r2.status_code == 200
    second_count = len(r2.get_json()["blacklist"])
    
    # Should not increase count
    assert first_count == second_count


def test_add_blacklist_word_missing_word(client):
    """Test adding empty word."""
    r = client.post("/api/blacklist", json={})
    assert r.status_code == 400
    data = r.get_json()
    assert data["error"] == "word is required"


def test_remove_blacklist_word(client):
    """Test removing a word from blacklist."""
    # Add a word first
    client.post("/api/blacklist", json={"word": "remove_me"})
    
    # Remove it
    r = client.delete("/api/blacklist?word=remove_me")
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True
    assert "remove_me" not in data["blacklist"]


def test_remove_blacklist_word_not_exists(client):
    """Test removing a word that doesn't exist."""
    r = client.delete("/api/blacklist?word=nonexistent")
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True
    # Should succeed but no change


def test_remove_blacklist_word_missing_param(client):
    """Test removing without word parameter."""
    r = client.delete("/api/blacklist")
    assert r.status_code == 400
    data = r.get_json()
    assert data["error"] == "word is required"


def test_blacklist_round_trip(client):
    """Test full add/get/remove cycle."""
    # Add multiple words
    words = ["word1", "word2", "word3"]
    for word in words:
        client.post("/api/blacklist", json={"word": word})
    
    # Get blacklist
    r = client.get("/api/blacklist")
    assert r.status_code == 200
    blacklist = r.get_json()["blacklist"]
    for word in words:
        assert word in blacklist
    
    # Remove one word
    client.delete("/api/blacklist?word=word2")
    r = client.get("/api/blacklist")
    blacklist = r.get_json()["blacklist"]
    assert "word1" in blacklist
    assert "word2" not in blacklist
    assert "word3" in blacklist