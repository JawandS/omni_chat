"""
Omni Chat Architecture Overview
==============================

This document provides a comprehensive overview of the Omni Chat application
architecture, design patterns, and component interactions.

## System Overview

Omni Chat is a lightweight, locally-hosted web application that provides a unified
interface for interacting with multiple AI providers. The application follows a
modular, layered architecture with clear separation of concerns.

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (HTML/JS)                     │
├─────────────────────────────────────────────────────────────┤
│                    Flask Web Server                        │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐ │
│  │  Chat Logic  │ │  Database    │ │  Provider Adapters   │ │
│  │   (chat.py)  │ │ (database.py)│ │    (OpenAI, Gemini)  │ │
│  └──────────────┘ └──────────────┘ └──────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│                     SQLite Database                        │
└─────────────────────────────────────────────────────────────┘
```

## Module Architecture

### 1. Web Layer (app.py)
**Responsibility**: HTTP request handling, routing, and response formatting

**Key Features**:
- Flask application factory pattern
- RESTful API endpoints
- Template rendering for UI
- Request validation and error handling
- Session management

**API Endpoints**:
- `/api/chat` - Main chat interface
- `/api/chats/*` - Chat management (CRUD)
- `/api/projects/*` - Project organization
- `/api/tasks/*` - Task scheduling
- `/api/keys/*` - API key management

### 2. Chat Logic Layer (chat.py)
**Responsibility**: AI provider interaction and response handling

**Key Features**:
- Provider abstraction layer
- Unified response format
- Streaming and non-streaming support
- Error handling across providers
- Special model handling (reasoning, web search)

**Supported Providers**:
- OpenAI (GPT models, reasoning models, web search)
- Google Gemini (Gemini models)
- Ollama (Local models)

### 3. Data Layer (database.py)
**Responsibility**: Data persistence and retrieval

**Key Features**:
- SQLite connection management
- CRUD operations for all entities
- Database migration support
- Transaction handling
- UTC timestamp consistency

**Database Schema**:
```sql
chats(id, title, provider, model, created_at, updated_at, project_id)
messages(id, chat_id, role, content, provider, model, timestamp)
projects(id, name, created_at, updated_at)
tasks(id, name, description, date, time, frequency, provider, model, ...)
```

### 4. Utilities Layer (utils.py)
**Responsibility**: Shared functionality and configuration management

**Key Components**:
- Request validation
- Environment management
- Provider configuration
- Common utilities

### 5. Email Service (email_service.py)
**Responsibility**: Email notifications and task result delivery

**Key Features**:
- SMTP configuration management
- HTML email composition
- Multi-provider support
- Secure authentication

## Design Patterns

### 1. Application Factory Pattern
```python
def create_app() -> Flask:
    app = Flask(__name__)
    # Configure app
    db_init_app(app)
    return app
```

**Benefits**:
- Enables easy testing with different configurations
- Supports multiple app instances
- Clean dependency injection

### 2. Provider Adapter Pattern
```python
def generate_reply(message, history, provider, model, params=None):
    if provider == "openai":
        return _openai_call(message, history, model, params)
    elif provider == "gemini":
        return _gemini_call(message, history, model, params)
    # ... other providers
```

**Benefits**:
- Uniform interface across different AI providers
- Easy to add new providers
- Consistent error handling

### 3. Data Access Object (DAO) Pattern
```python
def create_chat(title, provider, model, now=None):
    # Database operations encapsulated
    # Returns consistent data format
```

**Benefits**:
- Separation of business logic from data access
- Consistent data operations
- Easy to test and mock

### 4. Configuration Manager Pattern
```python
class EnvironmentManager:
    def get_api_keys(self):
        # Centralized configuration access
```

**Benefits**:
- Centralized configuration management
- Environment-specific settings
- Secure credential handling

## Data Flow

### 1. Chat Request Flow
```
User Input → Frontend → Flask Route → Validation → Chat Logic → 
Provider API → Response Processing → Database Storage → 
JSON Response → Frontend Update
```

### 2. Database Operations Flow
```
Request → Validation → Database Function → SQLite → 
Row Processing → Response Object → JSON Serialization
```

### 3. Configuration Flow
```
Environment Files → EnvironmentManager → Application Config → 
Runtime Access → Provider Clients → API Calls
```

## Security Architecture

### 1. Input Validation
- All user inputs validated at the API layer
- SQL injection prevention through parameterized queries
- XSS prevention through template escaping

### 2. API Key Management
- Environment-based key storage
- No keys in source code or logs
- Isolated test environments

### 3. Database Security
- Local SQLite file with appropriate permissions
- No remote database connections
- Transaction isolation

### 4. Network Security
- HTTPS support for production
- CORS configuration
- Rate limiting considerations

## Scalability Considerations

### Current Scale
- Single-user desktop application
- Local SQLite database
- Synchronous request processing

### Potential Improvements
- Database connection pooling
- Async request processing
- Caching layer for provider responses
- Background task processing

## Testing Architecture

### Test Isolation
- Temporary databases per test
- Mocked external dependencies
- Isolated configuration files

### Test Categories
- Unit tests for individual functions
- Integration tests for API endpoints
- End-to-end tests for user workflows

### Safety Mechanisms
- Production database protection
- No real API calls during testing
- Automatic cleanup of test resources

## Deployment Architecture

### Local Development
```
Python Virtual Environment → Flask Dev Server → SQLite Database
```

### Production Options
```
Python Environment → WSGI Server (Gunicorn) → Reverse Proxy (Nginx) → 
SQLite/PostgreSQL Database
```

## Configuration Management

### Environment Variables
- `OPENAI_API_KEY`: OpenAI API authentication
- `GEMINI_API_KEY`: Google Gemini API authentication
- `SMTP_*`: Email configuration settings

### Configuration Files
- `static/providers.json`: AI provider and model definitions
- `.env`: Environment-specific settings
- `instance/omni_chat.db`: SQLite database file

## Error Handling Strategy

### Layered Error Handling
1. **Input Validation**: Catch invalid requests early
2. **Provider Errors**: Handle API failures gracefully
3. **Database Errors**: Manage connection and constraint issues
4. **Application Errors**: Log and return user-friendly messages

### Error Response Format
```json
{
  "error": "Human-readable error message",
  "missing_key_for": "provider_name",  // If API key missing
  "details": "Technical details for debugging"
}
```

## Performance Considerations

### Response Times
- Chat responses: 1-10 seconds (dependent on provider)
- Database operations: <100ms
- Static file serving: <50ms

### Memory Usage
- Base application: ~50MB
- Per chat session: ~1-5MB
- Database: Grows with chat history

### Optimization Opportunities
- Response caching for repeated queries
- Database indexing for chat history
- Lazy loading of provider clients
- Connection pooling for high usage

---

This architecture provides a solid foundation for a maintainable, testable, and
extensible chat application while keeping complexity manageable for a desktop
application use case.
"""
