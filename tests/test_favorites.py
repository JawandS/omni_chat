"""Tests for favorites and d    # Remove favorite
rem = client.delete("/api/favorites?provider=openai&model=gpt-4o")
assert rem.status_code == 200
favs3 = rem.get_json()["favorites"]
assert "openai:gpt-4o" not in favs3t model provider configuration endpoints."""

import json
from pathlib import Path


def test_get_initial_favorites(client):
    r = client.get("/api/favorites")
    assert r.status_code == 200
    data = r.get_json()
    assert "favorites" in data
    assert isinstance(data["favorites"], list)
    assert "default" in data


def test_add_and_remove_favorite_round_trip(client):
    # Add a favorite (choose one known from providers_template.json)
    add = client.post("/api/favorites", json={"provider": "openai", "model": "gpt-4o"})
    assert add.status_code == 200
    favs = add.get_json()["favorites"]
    assert "openai:gpt-4o" in favs

    # Idempotent add
    add2 = client.post("/api/favorites", json={"provider": "openai", "model": "gpt-4o"})
    assert add2.status_code == 200
    favs2 = add2.get_json()["favorites"]
    assert favs2.count("openai:gpt-4o") == 1

    # Remove favorite
    rem = client.delete("/api/favorites?provider=openai&model=gpt-4o")
    assert rem.status_code == 200
    favs3 = rem.get_json()["favorites"]
    assert "openai:gpt-4o-mini" not in favs3


def test_add_favorite_missing_fields(client):
    r = client.post("/api/favorites", json={"provider": "openai"})
    assert r.status_code == 400
    assert r.get_json()["error"] == "provider and model required"

    r2 = client.post("/api/favorites", json={"model": "gpt-4o-mini"})
    assert r2.status_code == 400
    assert r2.get_json()["error"] == "provider and model required"


def test_remove_favorite_missing_params(client):
    r = client.delete("/api/favorites")
    assert r.status_code == 400
    assert r.get_json()["error"] == "provider and model required"


def test_add_favorite_unknown_model(client):
    r = client.post(
        "/api/favorites", json={"provider": "openai", "model": "no-such-model"}
    )
    assert r.status_code == 400
    assert r.get_json()["error"] == "unknown provider/model"


def test_set_default_model_invalid(client):
    r = client.put(
        "/api/default-model", json={"provider": "openai", "model": "does-not-exist"}
    )
    assert r.status_code == 400
    assert r.get_json()["error"] == "unknown provider/model"

    r2 = client.put("/api/default-model", json={"provider": "", "model": ""})
    assert r2.status_code == 400
    assert r2.get_json()["error"] == "provider and model required"


def test_providers_config_endpoint(client):
    r = client.get("/api/providers-config")
    assert r.status_code == 200
    data = r.get_json()
    # Should have providers list and favorites structure
    assert "providers" in data
    assert isinstance(data["providers"], list)
    assert "favorites" in data
    assert "default" in data
