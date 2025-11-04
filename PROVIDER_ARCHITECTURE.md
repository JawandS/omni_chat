# Provider & Model Architecture - Technical Reference

## Overview

The provider architecture uses an **adapter pattern** where each AI provider (OpenAI, Gemini, Ollama) has its own implementation, but they all conform to a unified interface through the `generate_reply()` function.

---

## Architecture Pattern: Provider Adapter

### Main Entry Point

**File:** `/home/user/omni_chat/chat.py`

```python
def generate_reply(
    provider: str,
    model: str,
    message: str,
    history: Optional[List[Dict[str, str]]] = None,
    params: Optional[Dict[str, Any]] = None,
) -> ChatReply:
    """Generate a chat response using the specified provider."""
    
    if provider_lower == "openai":
        return ChatReply(reply=_openai_call(...)) or error
    elif provider_lower == "gemini":
        return ChatReply(reply=_gemini_call(...)) or error
    elif provider_lower == "ollama":
        return ChatReply(reply=_ollama_call(...)) or error
    else:
        raise ValueError(f"unknown provider: {provider}")
```

### Response Type

```python
@dataclass
class ChatReply:
    reply: str
    warning: Optional[str] = None
    error: Optional[str] = None
    missing_key_for: Optional[str] = None
```

---

## Provider Implementation Pattern

Each provider has the same structure:

### 1. History Formatter

Converts the unified history format to the provider's expected format:

```python
def _format_history_for_PROVIDER(
    history: List[Dict[str, str]], 
    latest_message: str
) -> PROVIDER_HISTORY_TYPE:
    """Convert unified format to provider-specific format."""
    # OpenAI: List of {"role": "user"|"assistant", "content": str}
    # Gemini: (List of {"role": "user"|"model", "parts": [str]}, user_text)
    # Ollama: List of {"role": "user"|"assistant", "content": str}
```

### 2. Provider-Specific Call

```python
def _PROVIDER_call(
    model: str,
    history: List[Dict[str, str]],
    message: str,
    params: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Call the provider API and return response text."""
    
    # Get API key
    key = get_api_key("PROVIDER")
    if not key:
        return None
    
    # Format history
    formatted_history = _format_history_for_PROVIDER(history, message)
    
    # Filter allowed parameters for this provider
    allowed_params = {...}  # Provider-specific parameters
    call_params = {k: params[k] for k in allowed_params if k in params}
    
    # Make API call
    response = provider_client.chat.create(
        model=model,
        messages=formatted_history,
        **call_params
    )
    
    # Extract and return response text
    return extract_response_text(response)
```

---

## Current Provider Implementations

### 1. OpenAI Provider

**File Location:** `chat.py` lines 197-306

**API Client:** `openai.OpenAI`

**Import:**
```python
from openai import OpenAI
```

**Key Functions:**
- `_format_history_for_openai()` - Convert to messages list
- `_is_reasoning_model()` - Detect o3 series models
- `_is_thinking_model()` - Detect gpt-5-thinking
- `_is_live_model()` - Detect gpt-4.1-live
- `_supports_thinking_budget_tokens()` - Check parameter support
- `_openai_call()` - Main API call

**Special Model Handling:**

```
Reasoning Models (o3, o3-pro, o3-mini):
├─ Uses: client.responses.create() (not chat.completions)
├─ Params: reasoning_effort="low|medium|high"
└─ Special: Returns output_text not choices[0].message.content

Thinking Models (gpt-5-thinking):
├─ Uses: client.responses.create()
├─ Params: reasoning_effort, verbosity
└─ Special: Extended thinking output

Live Models (gpt-4.1-live):
├─ Uses: client.responses.create()
├─ Tools: [{"type": "web_search"}]
└─ Special: Web search capability

Standard Models (gpt-4o, etc.):
├─ Uses: client.chat.completions.create()
├─ Params: temperature, top_p, max_tokens, etc.
└─ Standard: choices[0].message.content
```

**Supported Parameters:**
```
temperature      (0-2)
top_p           (0-1)
max_tokens      (integer)
presence_penalty (-2 to 2)
frequency_penalty (-2 to 2)
seed            (integer)
stop            (string or array)
response_format (JSON schema)
reasoning_effort (low|medium|high)  # for o3, gpt-5-thinking
verbosity       (brief|medium|verbose)  # for gpt-5-thinking
thinking_budget_tokens  # for o1 series and gpt-5-thinking
```

**Available Models:**
```
gpt-4.1-live         (web search)
gpt-5-chat-latest    (latest)
gpt-5-mini          (efficient)
gpt-5-nano          (smallest)
gpt-4o              (general)
gpt-5-thinking      (extended thinking)
o3                  (reasoning)
o3-pro             (advanced reasoning)
o3-mini            (efficient reasoning)
```

---

### 2. Google Gemini Provider

**File Location:** `chat.py` lines 308-530

**API Clients:** 
- `google.generativeai` (standard models)
- `google.genai` (live search models)

**Imports:**
```python
import google.generativeai as genai
from google import genai as google_genai
from google.genai import types as genai_types
```

**Key Functions:**
- `_format_history_for_gemini()` - Convert to Gemini format
- `_gemini_call()` - Standard models
- `_gemini_live_call()` - Models with web search grounding

**Message Format:**
```python
# Gemini format
{
    "role": "user" | "model",  # Note: "model" not "assistant"
    "parts": ["text content"]   # Array, not single string
}
```

**Special Model Handling:**

```
Live Models (gemini-2.5-pro-live):
├─ Uses: google.genai API (new)
├─ Tools: [Tool(google_search=GoogleSearch())]
└─ Special: Grounding metadata with sources

Standard Models (gemini-2.5-flash, etc.):
├─ Uses: google.generativeai API (legacy)
├─ Safety: Handles finish_reason (SAFETY, RECITATION)
└─ Standard: Extract from candidates[0]
```

**Supported Parameters:**
```
temperature        (0-2)
top_p             (0-1)
top_k             (integer)
max_output_tokens (integer)
web_search        (boolean)  # via tools in live search
```

**Available Models:**
```
gemini-2.5-pro-live      (web search grounding)
gemini-2.5-flash-lite    (lightweight)
gemini-2.5-pro           (general purpose)
gemini-2.5-flash         (fast)
gemini-2.0-flash         (legacy)
gemini-1.5-pro           (legacy)
gemini-1.5-flash         (legacy)
```

**Safety Handling:**
```python
# Gemini responses include finish_reason
finish_reason == 1:  # STOP - normal
finish_reason == 2:  # MAX_TOKENS - truncated
finish_reason == 3:  # SAFETY - filtered
finish_reason == 4:  # RECITATION - citations
finish_reason == 5:  # OTHER - error

# Response includes grounding metadata
if hasattr(response, 'grounding_metadata'):
    # Extract search results and append as sources
```

---

### 3. Ollama Provider (Local)

**File Location:** `chat.py` lines 532-652

**API Method:** HTTP requests to local Ollama server

**Imports:**
```python
import requests
from utils import (
    is_ollama_available,
    is_ollama_server_running,
    start_ollama_server,
    get_ollama_models,
)
```

**Key Functions:**
- `_format_history_for_ollama()` - Standard message format
- `_ollama_call()` - HTTP call to local server
- `is_ollama_available()` - Check if installed
- `is_ollama_server_running()` - Health check
- `start_ollama_server()` - Auto-start service
- `get_ollama_models()` - Discover available models

**API Endpoint:**
```
POST http://localhost:11434/api/chat
```

**Request Format:**
```json
{
    "model": "model-name",
    "messages": [
        {"role": "user|assistant", "content": "..."}
    ],
    "stream": false,
    "options": {
        "temperature": 0.7,
        "top_p": 0.9,
        "top_k": 40,
        "num_predict": 2048  // max_tokens
    }
}
```

**Response Format:**
```json
{
    "message": {
        "role": "assistant",
        "content": "response text"
    }
}
```

**Supported Parameters:**
```
temperature      (0-2)
top_p           (0-1)
top_k           (integer)
max_tokens      → num_predict (integer)
```

**Model Discovery:**
```
GET http://localhost:11434/api/tags

Response:
{
    "models": [
        {"name": "llama3.2:latest", ...},
        {"name": "mistral:latest", ...}
    ]
}
```

**Available Models** (auto-discovered, examples):
```
llama3.2          (3B - fastest)
llama3.2:8b       (8B - balanced)
llama3.1:70b      (70B - highest quality)
mistral:latest    (alternative)
codellama         (code-specialized)
phi3              (Microsoft efficient)
```

---

## Configuration System

### Provider Definition File

**Location:** `/home/user/omni_chat/static/providers_template.json`

```json
{
  "default": {
    "provider": "gemini",
    "model": "gemini-2.5-flash"
  },
  "favorites": [
    "gemini:gemini-2.5-flash",
    "openai:gpt-5-chat-latest"
  ],
  "providers": [
    {
      "id": "gemini",
      "name": "Google Gemini",
      "models": [
        "gemini-2.5-pro-live",
        "gemini-2.5-flash-lite",
        "gemini-2.5-pro",
        "gemini-2.5-flash"
      ]
    },
    {
      "id": "openai",
      "name": "OpenAI",
      "models": [
        "gpt-4.1-live",
        "gpt-5-chat-latest",
        "gpt-5-mini",
        "gpt-4o",
        "o3"
      ]
    }
  ],
  "blacklist": []
}
```

### Runtime Configuration

**Location:** `/home/user/omni_chat/static/providers.json` (generated)

Created from template on first run, dynamically updated with Ollama models if available.

**ProvidersConfigManager** (in utils.py):
```python
class ProvidersConfigManager:
    def load_providers_json(self) -> dict
    def write_providers_json(self, data: dict) -> None
    def validate_provider_model(self, provider: str, model: str) -> bool
```

### API Key Management

**Class:** `EnvironmentManager` (in utils.py)

**Storage:** `.env` file or environment variables

**Managed Keys:**
```
OPENAI_API_KEY    → openai provider
GEMINI_API_KEY    → gemini provider
(ollama needs no key)
```

**Function:** `get_api_key(provider: str) -> str`

Returns empty string if not configured, "local" for Ollama.

---

## API Endpoints for Provider Management

### Get Provider Configuration

```
GET /api/providers

Returns:
{
  "default": {"provider": "gemini", "model": "gemini-2.5-flash"},
  "providers": [
    {
      "id": "openai",
      "name": "OpenAI",
      "models": [...]
    },
    ...
  ],
  "blacklist": []
}
```

### Get Model Parameter Schema

```
GET /api/model-config?provider=openai&model=gpt-4o

Returns:
{
  "provider": "openai",
  "model": "gpt-4o",
  "params": [
    {
      "name": "temperature",
      "type": "number",
      "min": 0,
      "max": 2,
      "step": 0.01,
      "default": 1.0,
      "label": "Temperature"
    },
    ...
  ]
}
```

---

## Parameter Handling

### Parameter Flow

```
Frontend sends: {"params": {"temperature": 0.7, "max_tokens": 500}}
    ↓
App validates against provider's supported parameters
    ↓
Chat.py filters allowed parameters
    ↓
Provider-specific formatting
    ↓
API call with filtered parameters
```

### Allowed Parameters per Provider

**OpenAI:**
```
temperature, top_p, max_tokens, presence_penalty, 
frequency_penalty, seed, stop, response_format,
reasoning_effort, verbosity, thinking_budget_tokens
```

**Gemini:**
```
temperature, top_p, top_k, max_output_tokens
```

**Ollama:**
```
temperature, top_p, top_k, max_tokens (→ num_predict)
```

---

## Adding a New Provider

### Step 1: Create Provider Adapter

In `chat.py`:

```python
def _format_history_for_newprovider(
    history: List[Dict[str, str]], 
    latest_message: str
) -> NEW_FORMAT:
    """Format history for new provider."""
    # Convert to provider's expected format
    formatted = []
    for m in history or []:
        formatted.append(format_message(m))
    formatted.append({"role": "user", "content": latest_message})
    return formatted

def _newprovider_call(
    model: str,
    history: List[Dict[str, str]],
    message: str,
    params: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Call new provider API."""
    key = get_api_key("newprovider")
    if not key or key.startswith("PUT_"):
        return None
    
    formatted = _format_history_for_newprovider(history, message)
    params = params or {}
    
    # Define allowed parameters
    allowed = {"temperature", "top_p", "max_tokens"}
    call_params = {k: params[k] for k in allowed if k in params}
    
    # Make API call
    client = NewProviderClient(api_key=key)
    response = client.chat(model=model, messages=formatted, **call_params)
    
    # Extract response text
    return extract_response(response)

# Add to generate_reply()
elif provider_lower == "newprovider":
    try:
        content = _newprovider_call(model, history, message, params=params)
        if content:
            return ChatReply(reply=content)
        key = get_api_key("newprovider")
        if not key or key.startswith("PUT_"):
            return ChatReply(
                reply="", 
                error="New Provider API key not set",
                missing_key_for="newprovider"
            )
        return ChatReply(reply="", error="New Provider returned no content")
    except Exception as e:
        return ChatReply(
            reply="", 
            error=f"New Provider error: {e.__class__.__name__}: {e}"
        )
```

### Step 2: Update Configuration

In `static/providers_template.json`:

```json
{
  "providers": [
    // ... existing providers
    {
      "id": "newprovider",
      "name": "New Provider",
      "models": ["model-1", "model-2", "model-3"]
    }
  ]
}
```

### Step 3: Update EnvironmentManager

In `utils.py`:

```python
class EnvironmentManager:
    def get_api_keys(self) -> Dict[str, str]:
        values = dotenv_values(self.env_path)
        newprovider_key = values.get("NEWPROVIDER_API_KEY")
        newprovider_key = newprovider_key or os.getenv("NEWPROVIDER_API_KEY", "")
        return {
            # ... existing
            "newprovider": newprovider_key or "",
        }
    
    def update_api_keys(self, keys_data: Dict[str, Any]) -> Dict[str, Optional[str]]:
        key_mapping = [
            # ... existing
            ("NEWPROVIDER_API_KEY", "newprovider"),
        ]
        # ... rest of method
    
    def delete_api_key(self, provider: str) -> bool:
        key_mapping = {
            # ... existing
            "newprovider": "NEWPROVIDER_API_KEY",
        }
        # ... rest of method
```

### Step 4: Add Tests

In `tests/test_chat.py`:

```python
def test_newprovider_chat(client):
    """Test chat with new provider."""
    response = client.post(
        "/api/chat",
        json={
            "message": "Hello",
            "provider": "newprovider",
            "model": "model-1"
        }
    )
    assert response.status_code == 200
    data = response.get_json()
    assert "reply" in data
    assert "chat_id" in data
```

---

## Error Handling

### API Key Errors

```python
key = get_api_key("provider")
if not key or key.startswith("PUT_") or CLIENT is None:
    return ChatReply(
        reply="",
        error="Provider API key not set",
        missing_key_for="provider"
    )
```

### Network/API Errors

```python
try:
    response = api_call(...)
    return ChatReply(reply=response)
except Exception as e:
    return ChatReply(
        reply="",
        error=f"Provider error: {e.__class__.__name__}: {e}"
    )
```

### No Content Errors

```python
if content:
    return ChatReply(reply=content)
return ChatReply(reply="", error="Provider returned no content")
```

---

## Testing Provider Integration

### Mock Setup (conftest.py)

```python
@pytest.fixture
def client():
    # ...
    with patch('chat.OpenAI') as mock_openai:
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        # Mock chat completion
        mock_completion = MagicMock()
        mock_completion.choices[0].message.content = "Test response"
        mock_client.chat.completions.create.return_value = mock_completion
        
        yield app.test_client()
```

### Test Pattern

```python
def test_provider_chat(client, mocker):
    """Test provider chat integration."""
    # Mock the provider call
    mock_call = mocker.patch('chat._provider_call')
    mock_call.return_value = "Mocked response"
    
    # Make request
    response = client.post(
        "/api/chat",
        json={
            "message": "Test",
            "provider": "provider",
            "model": "model"
        }
    )
    
    # Verify
    assert response.status_code == 200
    data = response.get_json()
    assert data["reply"] == "Mocked response"
    mock_call.assert_called_once()
```

---

## Key Integration Points

### 1. Parameter Validation

**File:** `app.py`, `/api/model-config` endpoint

Validates that requested parameters are supported by the model.

### 2. Provider-Specific Logic

**File:** `chat.py`

Each provider has its own:
- History formatter
- API call function
- Error handling
- Response parsing

### 3. Configuration Management

**File:** `utils.py`

- API key management
- Provider configuration loading
- Provider discovery (Ollama)

### 4. Database Storage

**File:** `database.py`

Each message stores:
- Provider used
- Model used
- Message content
- Timestamp

---

## Debugging Provider Issues

### Enable Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Provider-specific logging
logger = logging.getLogger(__name__)
logger.info(f"[PROVIDER] Starting request to model: {model}")
```

### Common Issues

**Issue:** "API key not set"
- Solution: Check `get_api_key()` retrieval, verify `.env` file

**Issue:** Model not found
- Solution: Check `providers.json`, verify model name in provider config

**Issue:** History format mismatch
- Solution: Verify history formatter produces correct structure

**Issue:** Parameter not supported
- Solution: Check allowed parameters list for that provider

