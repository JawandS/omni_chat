"""
Test Safety and Isolation Guide
===============================

This document outlines the comprehensive safety mechanisms implemented in the Omni Chat
test suite to ensure that tests never affect production data, make real API calls, or
interfere with the production environment.

## Core Safety Principles

1. **Complete Isolation**: Each test runs in complete isolation with its own database,
   configuration files, and environment.

2. **No External Calls**: All API calls to external services (OpenAI, Gemini, etc.)
   are mocked and intercepted.

3. **Temporary Resources**: All test resources are created in temporary directories
   and automatically cleaned up.

4. **Production Protection**: Production database and configuration files are never
   accessed during testing.

## Safety Mechanisms

### Database Isolation
- Each test gets a fresh SQLite database in a temporary directory
- Database path: `tmp_path / "test.db"` (unique per test)
- Production database at `instance/omni_chat.db` is never touched
- Database schema is recreated for each test ensuring clean state

### Configuration Isolation
- Temporary `.env` files created per test: `tmp_path / ".env.test"`
- Providers configuration copied from `static/providers_template.json`
- Environment variables safely overridden for test duration
- Production `.env` file is never modified

### API Call Mocking
```python
# All API clients are mocked to prevent real calls
monkeypatch.setattr(chat_mod, "OpenAI", None, raising=False)
monkeypatch.setattr(chat_mod, "genai", None, raising=False)

# API key getter always returns test values
def mock_get_api_key(provider):
    return "PUT_API_KEY_HERE" if provider.lower() in ["openai", "gemini"] else ""
```

### File System Isolation
- Tests use temporary directories that are automatically cleaned up
- Working directory isolation prevents affecting production files
- All file operations are contained within test-specific paths

## Test Structure

### conftest.py
The main test configuration file provides:
- `client` fixture: Flask test client with complete isolation
- Automatic resource cleanup after each test
- Provider configuration management
- API mocking setup

### Test Categories

1. **Unit Tests**: Test individual functions and methods
2. **Integration Tests**: Test API endpoints and database operations
3. **Isolation Tests**: Verify test safety mechanisms themselves
4. **UI Tests**: Test frontend functionality without real API calls

## Running Tests Safely

### Basic Test Run
```bash
pytest -q  # Run all tests quietly
```

### With Coverage
```bash
pytest --cov=. --cov-report=html
```

### Verbose Output
```bash
pytest -v  # Detailed test output
```

### Test a Specific Module
```bash
pytest tests/test_app.py -v
```

## Verification Commands

To verify test isolation is working:

```bash
# Check that production DB is not modified during tests
stat instance/omni_chat.db  # Should show no recent modifications

# Run tests and verify no network calls
pytest -v  # Should complete even without internet connection

# Verify temp files are cleaned up
ls /tmp/pytest-*  # Should be empty after test completion
```

## Common Test Patterns

### Testing API Endpoints
```python
def test_chat_endpoint(client):
    # This is safe - uses mocked providers
    response = client.post('/api/chat', json={
        'message': 'Hello',
        'provider': 'openai',
        'model': 'gpt-4o'
    })
    assert response.status_code == 200
```

### Testing Database Operations
```python
def test_database_operation(client):
    # Uses isolated test database
    from database import create_chat
    with client.application.app_context():
        chat_id = create_chat("Test", "openai", "gpt-4o")
        assert chat_id is not None
```

## Safety Checklist

Before running tests, verify:
- [ ] Production database exists at `instance/omni_chat.db`
- [ ] No API keys are set in the test environment
- [ ] Internet connection is not required for tests to pass
- [ ] Tests complete in under 10 seconds (no external delays)

After running tests, verify:
- [ ] Production database timestamp is unchanged
- [ ] No test files remain in the workspace
- [ ] No temporary directories remain in `/tmp`
- [ ] All 96+ tests passed without errors

## Emergency Procedures

If tests accidentally affect production:

1. **Stop immediately**: Ctrl+C to halt running tests
2. **Check database**: Verify `instance/omni_chat.db` integrity
3. **Restore backup**: Use git to restore any modified files
4. **Report issue**: Document what happened for investigation

## Debugging Test Issues

### Common Issues

1. **Import Errors**: Ensure virtual environment is activated
2. **Database Locked**: Check for zombie test processes
3. **Permission Errors**: Verify write permissions in test directory
4. **Assertion Failures**: Check test data and expectations

### Debug Commands
```bash
# Run single test with full output
pytest tests/test_app.py::test_specific_function -v -s

# Run with Python debugger
pytest --pdb tests/test_app.py::test_specific_function

# Check test coverage
pytest --cov=app --cov-report=term-missing
```

## Test Development Guidelines

When writing new tests:

1. **Always use the `client` fixture** for Flask app testing
2. **Never hardcode production paths** in test code
3. **Mock all external API calls** explicitly
4. **Verify test isolation** by running tests multiple times
5. **Test both success and error paths** for complete coverage
6. **Use descriptive test names** that explain what is being tested

## Continuous Integration

For CI/CD environments:
- Tests run in completely isolated containers
- No external network access required
- All dependencies mocked or provided locally
- Fast execution (under 30 seconds for full suite)
- Deterministic results regardless of external factors

---

This safety framework ensures that the Omni Chat test suite can be run confidently
in any environment without risk to production data or external services.
"""
