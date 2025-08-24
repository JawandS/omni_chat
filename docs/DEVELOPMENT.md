"""
Development Guide
================

This guide provides comprehensive information for developers working on the
Omni Chat application, including setup, development workflows, coding standards,
and contribution guidelines.

## Getting Started

### Prerequisites
- Python 3.10+ (tested on 3.12)
- Git for version control
- Basic knowledge of Flask, SQLite, and JavaScript

### Development Setup

1. **Clone the Repository**
```bash
git clone <repository-url>
cd omni_chat
```

2. **Create Virtual Environment**
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. **Install Dependencies**
```bash
# For runtime only
pip install -r requirements.txt

# For full development (recommended)
pip install -r requirements-dev.txt
```

4. **Configure Environment**
```bash
# Create .env file with your API keys
echo 'OPENAI_API_KEY=your-key-here' >> .env
echo 'GEMINI_API_KEY=your-key-here' >> .env
```

5. **Run the Application**
```bash
python app.py
# Open http://127.0.0.1:5000
```

## Development Workflow

### Daily Development
```bash
# Always activate virtual environment first
source .venv/bin/activate

# Run tests before making changes
pytest -q

# Make your changes...

# Run tests after changes
pytest -q

# Check code quality
black --check .
mypy . --ignore-missing-imports

# Format code if needed
black .
```

### Before Committing
```bash
# Run full test suite
pytest -v

# Check type safety
mypy . --ignore-missing-imports

# Ensure code is formatted
black --check .

# Verify application starts
python app.py  # Ctrl+C after confirming it starts
```

## Code Organization

### File Structure
```
omni_chat/
├── app.py              # Main Flask application
├── chat.py             # AI provider interactions
├── database.py         # Database operations
├── utils.py            # Shared utilities
├── email_service.py    # Email functionality
├── requirements*.txt   # Dependencies
├── static/             # Frontend assets
│   ├── providers.json  # Provider configuration
│   └── js/            # JavaScript modules
├── templates/          # HTML templates
│   ├── base.html      # Base template
│   ├── index.html     # Main chat interface
│   └── fragments/     # Reusable template parts
├── tests/             # Test suite
│   ├── conftest.py    # Test configuration
│   └── test_*.py      # Test modules
└── docs/              # Documentation
```

### Module Responsibilities

**app.py**: Flask application and route handlers
- Web server configuration
- API endpoint definitions
- Request/response handling
- Template rendering

**chat.py**: AI provider abstraction
- OpenAI integration
- Gemini integration
- Ollama integration
- Response formatting

**database.py**: Data persistence layer
- SQLite connection management
- CRUD operations
- Schema management
- Migration handling

**utils.py**: Shared functionality
- Request validation
- Configuration management
- Common utilities

## Coding Standards

### Python Code Style
- **Formatter**: Black (automatic formatting)
- **Type Checking**: MyPy with strict settings
- **Import Ordering**: isort (included in black)
- **Line Length**: 88 characters (Black default)

### Documentation Standards
- **Module Docstrings**: Comprehensive module-level documentation
- **Function Docstrings**: Google-style docstrings for all public functions
- **Type Hints**: All function parameters and return values
- **Comments**: Explain complex business logic, not obvious code

### Example Function Documentation
```python
def create_chat(title: str, provider: str, model: str, now: Optional[str] = None) -> int:
    """Create a new chat conversation.
    
    Args:
        title: Human-readable chat title
        provider: AI provider name (openai, gemini, etc.)
        model: Model identifier for the provider
        now: Optional timestamp override (for testing)
        
    Returns:
        The database ID of the created chat
        
    Raises:
        ValueError: If provider or model is invalid
        DatabaseError: If chat creation fails
    """
```

### JavaScript Standards
- **ES6+**: Use modern JavaScript features
- **Naming**: camelCase for variables and functions
- **Comments**: JSDoc-style comments for complex functions
- **Error Handling**: Proper try/catch blocks for async operations

## Testing Guidelines

### Test Categories

**Unit Tests**: Test individual functions
```python
def test_validate_chat_request():
    # Test a single function in isolation
    message, provider, model = validate_chat_request({
        'message': 'Hello',
        'provider': 'openai',
        'model': 'gpt-4o'
    })
    assert message == 'Hello'
```

**Integration Tests**: Test API endpoints
```python
def test_chat_api_endpoint(client):
    # Test full API workflow
    response = client.post('/api/chat', json={
        'message': 'Hello',
        'provider': 'openai',
        'model': 'gpt-4o'
    })
    assert response.status_code == 200
```

**Safety Tests**: Verify test isolation
```python
def test_database_isolation(client):
    # Ensure tests don't affect production
    # (See docs/TEST_SAFETY.md for details)
```

### Writing Good Tests
1. **Test names should describe what is being tested**
   - Good: `test_chat_api_returns_error_for_missing_message`
   - Bad: `test_chat_api`

2. **Use the `client` fixture for Flask app testing**
3. **Mock external dependencies**
4. **Test both success and error paths**
5. **Keep tests fast and deterministic**

### Running Tests
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_app.py

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test
pytest tests/test_app.py::test_specific_function -v
```

## Database Development

### Schema Changes
1. **Never modify existing columns directly**
2. **Add migration logic to `database.py`**
3. **Test migrations with existing data**
4. **Document schema changes**

### Example Migration
```python
def _migrate_to_v2(db):
    """Add project_id column to chats table."""
    try:
        db.execute("ALTER TABLE chats ADD COLUMN project_id INTEGER")
        db.execute("CREATE INDEX idx_chats_project ON chats(project_id)")
        commit()
    except sqlite3.OperationalError:
        # Column already exists
        pass
```

### Database Best Practices
- Always use parameterized queries
- Handle connection errors gracefully
- Use transactions for related operations
- Index frequently queried columns

## Frontend Development

### HTML/CSS Guidelines
- **Responsive Design**: Use Tailwind CSS classes
- **Accessibility**: Include ARIA labels and semantic HTML
- **Performance**: Minimize external dependencies
- **Browser Support**: Modern browsers (ES6+ support)

### JavaScript Guidelines
- **Modular Code**: Separate concerns into functions
- **Error Handling**: User-friendly error messages
- **API Calls**: Use async/await pattern
- **DOM Manipulation**: Query elements once, cache references

### Example API Call
```javascript
async function sendMessage(message, provider, model) {
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, provider, model })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('Failed to send message:', error);
        showErrorToast('Failed to send message');
        throw error;
    }
}
```

## Adding New Features

### Adding a New AI Provider

1. **Extend the provider configuration**
```json
// static/providers.json
{
  "providers": [
    {
      "id": "newprovider",
      "name": "New Provider",
      "models": ["model1", "model2"]
    }
  ]
}
```

2. **Implement provider logic**
```python
# chat.py
def _newprovider_call(message, history, model, params):
    """Implementation for new provider."""
    # Provider-specific API calls
    return ChatReply(reply="response", error=None)
```

3. **Add to main dispatch**
```python
# chat.py
def generate_reply(message, history, provider, model, params=None):
    if provider == "newprovider":
        return _newprovider_call(message, history, model, params)
    # ... existing providers
```

4. **Add tests**
```python
# tests/test_chat.py
def test_newprovider_integration(client):
    # Test the new provider integration
```

### Adding a New API Endpoint

1. **Define the route**
```python
# app.py
@app.route("/api/new-feature", methods=["POST"])
def api_new_feature():
    """Handle new feature requests."""
    try:
        data = request.get_json()
        # Validate input
        # Process request
        # Return response
        return jsonify({"result": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400
```

2. **Add database operations if needed**
```python
# database.py
def create_new_entity(name: str, data: dict) -> int:
    """Create a new entity in the database."""
    # Implementation
```

3. **Add frontend integration**
```javascript
// templates/fragments/script.html
async function callNewFeature(data) {
    const response = await fetch('/api/new-feature', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
    return await response.json();
}
```

4. **Write comprehensive tests**
```python
# tests/test_app.py
def test_new_feature_endpoint(client):
    # Test the new endpoint
```

## Performance Optimization

### Database Optimization
- Use indexes for frequently queried columns
- Limit result sets with pagination
- Use EXPLAIN QUERY PLAN to analyze queries
- Consider connection pooling for high load

### Frontend Optimization
- Lazy load chat history
- Debounce user input
- Cache provider configuration
- Minimize DOM manipulation

### Backend Optimization
- Cache provider responses (if appropriate)
- Use background tasks for long operations
- Implement request timeout handling
- Monitor memory usage

## Debugging

### Common Issues

**Import Errors**
```bash
# Ensure virtual environment is activated
source .venv/bin/activate
# Check Python path
python -c "import sys; print(sys.path)"
```

**Database Locked**
```bash
# Check for zombie processes
ps aux | grep python
# Kill if necessary
kill <process_id>
```

**API Key Issues**
```bash
# Check environment variables
python -c "import os; print(os.getenv('OPENAI_API_KEY', 'Not set'))"
```

### Debug Mode
```python
# Enable Flask debug mode (development only)
app.run(debug=True)
```

### Logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.debug("Debug message")
```

## Contributing

### Pull Request Process
1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes
4. Run the full test suite: `pytest`
5. Check code quality: `black --check . && mypy .`
6. Commit with descriptive messages
7. Push to your fork
8. Open a pull request

### Commit Message Format
```
type(scope): short description

Longer description if needed

- List specific changes
- Reference issues: Fixes #123
```

**Types**: feat, fix, docs, test, refactor, style, chore

### Code Review Checklist
- [ ] All tests pass
- [ ] Code is properly formatted
- [ ] Type hints are present
- [ ] Documentation is updated
- [ ] No breaking changes (or properly documented)
- [ ] Security considerations addressed

## Release Process

### Version Management
- Follow semantic versioning (MAJOR.MINOR.PATCH)
- Update version in relevant files
- Tag releases in git

### Pre-release Checklist
- [ ] All tests pass
- [ ] Documentation is up to date
- [ ] Performance is acceptable
- [ ] Security review completed
- [ ] Backup procedures tested

---

This development guide should provide everything needed to contribute effectively
to the Omni Chat project. For specific questions, refer to the documentation
in the `docs/` directory or reach out to the maintainers.
"""
