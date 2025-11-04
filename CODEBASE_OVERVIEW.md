# Omni Chat Codebase Structure Overview

## Executive Summary

Omni Chat is a lightweight, locally-hosted web chat interface that provides unified access to multiple AI providers. The codebase is well-structured with clear separation of concerns across 5 main Python modules, comprehensive test coverage, and proper documentation.

**Current Implementation Status:**
- Multiple provider support: OpenAI, Google Gemini, Ollama (local)
- Single Flask web server with SQLite database
- Modular architecture with provider adapter pattern
- Feature-complete chat, project management, and task scheduling

---

## Directory Structure

```
omni_chat/
├── app.py                    # Flask app & API routes (1,389 lines)
├── chat.py                   # AI provider integrations (757 lines)
├── database.py               # SQLite operations (742 lines)
├── utils.py                  # Shared utilities & config (611 lines)
├── email_service.py          # Email notifications (304 lines)
├── requirements.txt          # Runtime dependencies
├── requirements-dev.txt      # Development dependencies
├── docs/
│   ├── ARCHITECTURE.md      # Detailed architecture documentation
│   ├── DEVELOPMENT.md       # Development guidelines
│   └── TEST_SAFETY.md       # Test isolation mechanisms
├── static/
│   ├── providers_template.json  # Provider configuration template
│   ├── providers.json           # Generated provider config (runtime)
│   ├── favicon.png
│   └── js/
│       └── task-manager.js      # Frontend task scheduling
├── templates/
│   ├── index.html           # Main chat interface
│   ├── base.html            # Base template
│   ├── schedule.html        # Task scheduling interface
│   └── fragments/           # HTML components
│       ├── chat-script.html
│       ├── conversation.html
│       ├── header.html
│       ├── modals.html
│       ├── sidebar.html
│       └── task-modal.html
└── tests/
    ├── conftest.py          # Pytest configuration & fixtures
    ├── test_core.py         # Core functionality tests
    ├── test_app.py          # API endpoint tests
    ├── test_chat.py         # Chat generation tests
    ├── test_database.py     # Database operation tests
    ├── test_utils.py        # Utility function tests
    ├── test_isolation.py    # Test isolation verification
    └── test_favorites.py    # Favorites feature tests
```

---

## Core Components

### 1. **Web Layer (app.py - 1,389 lines)**
**Responsibility:** HTTP request handling, routing, and response formatting

**Key Features:**
- Flask application factory pattern
- RESTful API endpoints
- Template rendering
- Request validation and error handling
- Session management

**Main API Endpoints:**
```
POST   /api/chat                          # Send message & get reply
GET    /api/chats                         # List all chats
GET    /api/chats/<id>                    # Get specific chat with messages
PATCH  /api/chats/<id>                    # Update chat metadata
DELETE /api/chats/<id>                    # Delete chat
GET    /api/projects                      # List projects
POST   /api/projects                      # Create project
DELETE /api/projects/<id>                 # Delete project
GET    /api/projects/<id>/chats           # Get chats in project
POST   /api/chats/<id>/project            # Add chat to project
DELETE /api/chats/<id>/project            # Remove chat from project
GET    /api/tasks                         # List scheduled tasks
POST   /api/tasks                         # Create task
PATCH  /api/tasks/<id>                    # Update task
DELETE /api/tasks/<id>                    # Delete task
GET    /api/keys                          # Get API key status
POST   /api/keys                          # Set API keys
DELETE /api/keys/<provider>               # Delete API key
GET    /api/providers                     # Get provider configuration
GET    /api/model-config                  # Get model parameter schema
GET    /api/email                         # Get email configuration
POST   /api/email                         # Set email configuration
```

**Provider & Model Handling:**
- Dynamic provider configuration via `providers.json`
- Support for switching models mid-conversation
- Provider-specific parameter validation

### 2. **Chat Logic Layer (chat.py - 757 lines)**
**Responsibility:** AI provider interaction and response handling

**Key Components:**
- `ChatReply` dataclass for typed responses
- Provider-specific implementations:
  - `_openai_call()` - OpenAI API integration
  - `_gemini_call()` - Google Gemini API integration
  - `_gemini_live_call()` - Gemini with web search grounding
  - `_ollama_call()` - Local Ollama integration
- `generate_reply()` - Main entry point with error handling

**Special Model Handling:**
- **Reasoning Models** (o3, o3-mini): Uses Responses API
- **Thinking Models** (gpt-5-thinking): Uses extended thinking
- **Live Models** (gpt-4.1-live, gemini-2.5-pro-live): Web search capabilities
- **Budget Tokens**: thinking_budget_tokens parameter support

**Message History Formatting:**
- OpenAI: Converts to messages list with roles
- Gemini: Converts to chat history format with "model" role
- Ollama: Standard message list format

### 3. **Data Layer (database.py - 742 lines)**
**Responsibility:** Data persistence and retrieval

**Database Schema:**
```sql
-- Conversation metadata
chats(
  id INTEGER PRIMARY KEY,
  title TEXT,
  provider TEXT,
  model TEXT,
  project_id INTEGER,
  created_at TEXT,
  updated_at TEXT
)

-- Individual messages with provider tracking
messages(
  id INTEGER PRIMARY KEY,
  chat_id INTEGER,
  role TEXT (user|assistant),
  content TEXT,
  provider TEXT,
  model TEXT,
  created_at TEXT
)

-- Chat organization
projects(
  id INTEGER PRIMARY KEY,
  name TEXT UNIQUE,
  created_at TEXT,
  updated_at TEXT
)

-- Scheduled AI tasks
tasks(
  id INTEGER PRIMARY KEY,
  name TEXT,
  description TEXT,
  date TEXT,
  time TEXT,
  frequency TEXT (none|daily|weekly|monthly|yearly),
  provider TEXT,
  model TEXT,
  output TEXT (application|email),
  email TEXT,
  status TEXT (pending|running|completed|failed),
  last_run TEXT,
  next_run TEXT,
  created_at TEXT,
  updated_at TEXT
)
```

**Key Operations:**
- CRUD operations for all entities
- Transaction management with automatic commit
- UTC timestamp consistency
- Foreign key constraints with cascading deletes

### 4. **Configuration & Utilities Layer (utils.py - 611 lines)**
**Responsibility:** Shared functionality and configuration management

**Key Classes:**

**EnvironmentManager**
- Handles `.env` file operations
- API key management (OpenAI, Gemini)
- Email configuration management
- Dynamic environment variable loading

**ProvidersConfigManager**
- Loads/writes `providers.json`
- Validates provider-model combinations
- Falls back to template if config doesn't exist
- Runtime provider discovery (Ollama)

**Key Functions:**
- `validate_chat_request()` - Input validation
- `generate_chat_title()` - Auto-title generation
- `create_or_update_chat()` - Chat lifecycle management
- `get_api_key()` - Secure credential retrieval
- `escape_html()` - Security utility
- `get_timestamp()` - UTC formatting

**Ollama Integration:**
- `is_ollama_available()` - Check installation
- `is_ollama_server_running()` - Health check
- `start_ollama_server()` - Automatic startup
- `get_ollama_models()` - Model discovery
- `initialize_ollama_with_app()` - Startup initialization

### 5. **Email Service (email_service.py - 304 lines)**
**Responsibility:** Email notifications and task result delivery

**Features:**
- SMTP configuration management
- HTML email composition
- Multi-provider support
- Secure authentication with TLS
- Task result email delivery

---

## Currently Supported Models

### OpenAI Provider
```
- gpt-4.1-live          (with web search)
- gpt-5-chat-latest     (latest GPT-5)
- gpt-5-mini            (efficient GPT-5)
- gpt-5-nano            (smallest GPT-5)
- gpt-4o                (general purpose)
- gpt-5-thinking        (extended thinking)
- o3                    (reasoning model)
- o3-pro               (advanced reasoning)
- o3-mini              (reasoning model)
```

### Google Gemini Provider
```
- gemini-2.5-pro-live      (with web search grounding)
- gemini-2.5-flash-lite    (lightweight)
- gemini-2.5-pro           (general purpose)
- gemini-2.5-flash         (fast inference)
- gemini-2.0-flash         (legacy)
- gemini-1.5-pro           (legacy)
- gemini-1.5-flash         (legacy)
```

### Ollama Provider (Local)
- Any model available in local Ollama installation
- Automatically discovered at runtime
- No API key required

### Provider Configuration File

The `providers_template.json` defines available providers and models:

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
      "models": ["gemini-2.5-pro-live", "gemini-2.5-flash-lite", ...]
    },
    {
      "id": "openai",
      "name": "OpenAI",
      "models": ["gpt-4.1-live", "gpt-5-chat-latest", ...]
    }
  ],
  "blacklist": []  // Models to hide from UI
}
```

---

## Design Patterns

### 1. **Application Factory Pattern**
```python
def create_app() -> Flask:
    app = Flask(__name__)
    db_init_app(app)
    # ... route registration
    return app
```
Benefits: Testability, multiple instances, clean DI

### 2. **Provider Adapter Pattern**
```python
def generate_reply(provider, model, message, history, params):
    if provider == "openai":
        return _openai_call(model, history, message, params)
    elif provider == "gemini":
        return _gemini_call(model, history, message, params)
    elif provider == "ollama":
        return _ollama_call(model, history, message, params)
```
Benefits: Uniform interface, easy to add providers, consistent error handling

### 3. **Data Access Object (DAO) Pattern**
All database operations encapsulated in `database.py`:
- `create_chat()`, `update_chat()`, `delete_chat()`
- `insert_message()`, `get_messages()`
- `create_project()`, `list_projects()`
- `create_task()`, `update_task()`

Benefits: Separation of concerns, testability, consistency

### 4. **Configuration Manager Pattern**
```python
class EnvironmentManager:
    def get_api_keys(self) -> Dict[str, str]
    def update_api_keys(self, keys: Dict)
    
class ProvidersConfigManager:
    def load_providers_json() -> dict
    def validate_provider_model(provider, model) -> bool
```
Benefits: Centralized config, environment isolation, security

---

## Data Flow

### Chat Request Flow
```
User Input
    ↓
Frontend (HTML/JS)
    ↓
POST /api/chat
    ↓
validate_chat_request() → extract message/provider/model
    ↓
create_or_update_chat() → get or create chat ID
    ↓
insert_message() → save user message to DB
    ↓
generate_reply() → call appropriate provider
    ├─ _openai_call() / _gemini_call() / _ollama_call()
    ├─ Format history for provider
    ├─ Make API call with parameters
    └─ Handle errors/special model logic
    ↓
insert_message() → save assistant reply to DB
    ↓
touch_chat() & commit() → update timestamps
    ↓
JSON Response → Frontend Update
```

### Configuration Flow
```
Environment Files (.env)
    ↓
EnvironmentManager
    ├─ Load env variables
    ├─ Get/set API keys
    └─ Manage SMTP config
    ↓
Runtime Access
    ↓
Provider Clients
    ↓
API Calls
```

### Provider Discovery Flow
```
App Startup
    ↓
initialize_ollama_with_app()
    ├─ Check if Ollama installed
    ├─ Check if server running
    ├─ Auto-start if available
    └─ Get available models
    ↓
ProvidersConfigManager
    ├─ Load providers_template.json
    ├─ Add Ollama provider if available
    └─ Write to providers.json
    ↓
Frontend Loads /api/providers
    ├─ Gets current provider list
    └─ Shows available models
```

---

## Key Features & Implementation Details

### Multi-Model Support
- **Mid-conversation switching**: Can change provider/model on each message
- **Model-specific parameters**: Each model supports different parameters
- **Provider metadata**: API endpoint `/api/model-config` provides parameter schemas

### Project Organization
- Group related chats
- Track project metadata
- Cascading deletion (project delete doesn't delete chats)

### Task Scheduling
- Recurring AI tasks (one-time, daily, weekly, monthly, yearly)
- Output to application or email
- Task status tracking (pending, running, completed, failed)

### API Key Management
- Environment-based storage
- Via `.env` file or web UI
- No keys in logs or source code
- Per-provider configuration

### Message History Tracking
- Each message stores provider and model
- Allows detection of model switches
- Supports switching back to previous models

---

## Security Architecture

### Input Validation
- All user inputs validated at API layer
- SQL injection prevention via parameterized queries
- XSS prevention via template escaping

### API Key Management
- Environment variables only
- Never logged or stored in DB
- Secure retrieval with `get_api_key()`

### Database Security
- Local SQLite file
- No remote connections
- Foreign key constraints enabled
- Transaction isolation

### Test Isolation
- Temporary databases per test
- Mocked external dependencies
- Isolated configuration files
- No real API calls during testing

---

## Dependencies

### Runtime (requirements.txt)
```
Flask>=3.0,<4
python-dotenv>=1.0.1
openai>=1.35.0
google-generativeai>=0.7.0
google-genai>=0.3.0
requests>=2.28.0
```

### Development (requirements-dev.txt)
```
(All runtime deps)
pytest>=7.4
pytest-cov>=4.1.0
black>=23.0.0
flake8>=6.0.0
mypy>=1.5.0
pre-commit>=3.4.0
```

---

## Testing Architecture

### Test Organization
- **test_core.py**: Core functionality (chats, messages, projects)
- **test_app.py**: API endpoint tests
- **test_chat.py**: Provider integration tests
- **test_database.py**: Database operations
- **test_utils.py**: Utility functions
- **test_isolation.py**: Test isolation verification
- **test_favorites.py**: Favorites feature

### Test Safety Features
- Separate test database
- Mocked API calls
- Temporary config files
- Automatic cleanup
- No production data access

### Running Tests
```bash
pytest -q                          # Quick test run
pytest -v                          # Verbose
pytest --cov=. --cov-report=html  # With coverage
pytest tests/test_core.py          # Specific test file
```

---

## Recent Development (from git log)

Latest commits show focus on:
1. **Model Integration**: API call adjustments, reasoning models
2. **Documentation**: Ollama docs, architecture docs
3. **Email Configuration**: SMTP setup, task notifications
4. **Project Management**: Auto-add chats to projects
5. **Live Models**: Web search integration (GPT-4.1 Live, Gemini Live)

---

## Architecture Overview Diagram

```
┌─────────────────────────────────────────────────────────┐
│                 Frontend (HTML/JS)                      │
│            (index.html, schedule.html)                  │
└────────────────────┬────────────────────────────────────┘
                     │
                     │ HTTP/JSON
                     ↓
┌─────────────────────────────────────────────────────────┐
│            Flask Web Server (app.py)                    │
│  - Route handlers                                       │
│  - Request validation                                   │
│  - Response formatting                                  │
└────┬─────────┬─────────┬──────────┬────────────────────┘
     │         │         │          │
     ↓         ↓         ↓          ↓
┌────────┐ ┌──────┐ ┌───────┐ ┌──────────┐
│ chat.py│ │db.py │ │utils. │ │email_    │
│        │ │      │ │py     │ │service.py│
│Provider│ │CRUD  │ │Config │ │          │
│Adapters│ │Ops   │ │Mgmt   │ │SMTP      │
└────┬───┘ └──┬───┘ └───┬───┘ └──────────┘
     │        │         │
     ↓        ↓         ↓
┌──────────────────────────────────────┐
│      External Services               │
├──────────────────────────────────────┤
│ OpenAI API     │ Google Gemini API   │
│ Ollama Server  │ Email Servers       │
└──────────────────────────────────────┘
     │        │
     ↓        ↓
┌──────────────────────────────────────┐
│    SQLite Database (omni_chat.db)   │
│                                      │
│  - chats                             │
│  - messages                          │
│  - projects                          │
│  - tasks                             │
└──────────────────────────────────────┘
```

---

## Scalability Considerations

### Current Limitations
- Single Flask process
- SQLite database (local)
- Synchronous request processing
- In-memory task scheduling

### Potential Improvements
- Database connection pooling
- Async request processing
- Caching layer for responses
- Background task processing (Celery)
- Multi-process deployment (Gunicorn)
- PostgreSQL for larger scale

---

## Key Files for Modernization

When modernizing for multi-model support, focus on:

1. **chat.py** - Provider adapter pattern is here
   - Add new providers following existing pattern
   - Each provider needs formatting and call functions

2. **providers_template.json** - Add new providers/models
   - Define provider metadata
   - List available models

3. **utils.py** - Configuration and Ollama integration
   - Update to support new provider credentials
   - Add new provider discovery mechanisms

4. **database.py** - May need schema extensions
   - Potentially track more model metadata
   - Support for additional provider-specific fields

5. **app.py** - API endpoints
   - `/api/model-config` provides parameter schemas
   - Validate new provider parameters

---

## Code Quality

- **Type Hints**: Throughout most of codebase
- **Documentation**: Comprehensive docstrings on all functions/classes
- **Testing**: Good coverage with isolated tests
- **Code Style**: Black formatting, mypy type checking
- **Patterns**: Consistent use of design patterns

---

## Next Steps for Modernization

1. **Review chat.py** to understand adapter pattern
2. **Study providers_template.json** for configuration structure
3. **Check utils.py** for credential/config management patterns
4. **Review ProvidersConfigManager** for model discovery
5. **Look at app.py** for API parameter handling
6. **Study test_chat.py** for provider testing patterns

