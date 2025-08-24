# Omni Chat

A lightweight, locally-hosted web chat interface that provides a unified way to interact with multiple AI providers. Switch between OpenAI, Google Gemini, and Ollama models mid-conversation while maintaining your chat history in a local SQLite database.

## ✨ Features

- **Multi-Provider Support**: OpenAI (GPT-4o, GPT-5, o3-mini), Google Gemini, and Ollama
- **Model Switching**: Change AI providers and models within the same conversation
- **Local Storage**: All chats stored locally in SQLite - your data stays private
- **Project Organization**: Group related chats into projects for better organization
- **Task Scheduling**: Schedule recurring AI tasks with email notifications
- **Email Integration**: Send task results via email with SMTP support
- **Responsive UI**: Clean, modern interface that works on desktop and mobile
- **Real-time Streaming**: Live response streaming for supported models
- **Web Search**: GPT-4.1 Live with real-time web search capabilities
- **Favorites System**: Quick access to your preferred model configurations

## 🚀 Quick Start

### Prerequisites
- Python 3.10+ (tested on Python 3.12)
- Git (for installation)

### Installation

1. **Clone and navigate to the project**
```bash
git clone <repository-url>
cd omni_chat
```

2. **Create a virtual environment**
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. **Install dependencies**
```bash
# For basic usage
pip install -r requirements.txt

# For development (includes testing, linting, type checking)
pip install -r requirements-dev.txt
```

4. **Start the application**
```bash
python app.py
```

5. **Open your browser**
Navigate to `http://127.0.0.1:5000`

6. **Configure API keys**
Click the settings icon (⚙️) and add your API keys, or create a `.env` file:
```bash
OPENAI_API_KEY=sk-your-openai-key-here
GEMINI_API_KEY=your-gemini-api-key-here
```

That's it! You can now start chatting with AI models.

## 🔧 Configuration

### API Keys

**Option 1: Via Web Interface**
- Click the settings icon (⚙️) in the top-right corner
- Switch to the "API Keys" tab
- Enter your keys and save

**Option 2: Via Environment File**
Create a `.env` file in the project root:
```env
OPENAI_API_KEY=sk-your-openai-key-here
GEMINI_API_KEY=your-gemini-api-key-here
```

### Email Setup (Optional)

Configure email for task notifications:

1. **Via Web Interface**: Settings → Email tab
2. **Via Environment File**:
```env
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_USE_TLS=true
FROM_EMAIL=your-email@gmail.com
```

**Gmail Setup**:
1. Enable 2-Factor Authentication
2. Generate an App Password at [Google App Passwords](https://myaccount.google.com/apppasswords)
3. Use the App Password in `SMTP_PASSWORD`

### Ollama Setup (Local AI Models)

Ollama allows you to run AI models locally on your machine, providing privacy and offline capabilities.

**Installation**:

1. **Install Ollama**
   ```bash
   # Linux/WSL
   curl -fsSL https://ollama.com/install.sh | sh
   
   # macOS
   brew install ollama
   
   # Or download from https://ollama.com/download
   ```

2. **Start Ollama service**
   ```bash
   # Start the Ollama service (runs on http://localhost:11434)
   ollama serve
   ```

3. **Install models**
   ```bash
   # Popular models (choose based on your hardware)
   ollama pull llama3.2        # 3B parameters - faster, less memory
   ollama pull llama3.2:8b     # 8B parameters - balanced
   ollama pull llama3.1:70b    # 70B parameters - high quality, requires more resources
   ollama pull codellama       # Code-specialized model
   ollama pull mistral         # Alternative high-quality model
   ollama pull phi3           # Microsoft's efficient model
   
   # List available models
   ollama list
   ```

4. **Configure in Omni Chat**
   - Ollama models will automatically appear in the provider dropdown
   - No API key required for Ollama
   - Default Ollama URL: `http://localhost:11434` (auto-detected)

**Hardware Requirements**:
- **Minimum**: 4GB RAM (for 3B models)
- **Recommended**: 8GB+ RAM (for 8B models) 
- **High-end**: 16GB+ RAM (for 70B+ models)
- **GPU**: Optional but significantly improves performance

**Model Selection Guide**:
- **llama3.2** (3B): Fast responses, good for basic tasks, low memory usage
- **llama3.2:8b**: Balanced performance and quality
- **llama3.1:70b**: Highest quality, requires substantial resources
- **codellama**: Optimized for code generation and analysis
- **mistral**: Alternative to Llama with good performance
- **phi3**: Microsoft's efficient model, good balance of size and capability

**Troubleshooting Ollama**:
- **Service not running**: Ensure `ollama serve` is running in background
- **Models not appearing**: Check that Ollama is accessible at `http://localhost:11434`
- **Slow responses**: Consider using smaller models or enabling GPU acceleration
- **Memory issues**: Use smaller models or increase system RAM

## 📖 User Guide

### Basic Usage

1. **Start a Chat**: Click "New Chat" or just start typing
2. **Switch Models**: Use the provider and model dropdowns at the top
3. **Organize Chats**: Create projects to group related conversations
4. **Schedule Tasks**: Use the "Schedule" page for recurring AI tasks
5. **Manage Settings**: Click the settings icon for configuration

### Advanced Features

**Project Management**:
- Create projects to organize related chats
- Assign chats to projects for better organization
- Delete projects (chats remain but become unassigned)

**Task Scheduling**:
- Schedule AI tasks to run automatically
- Choose output destination: application or email
- Set frequency: one-time, daily, weekly, monthly, yearly

**Model Configurations**:
- Save favorite model configurations for quick access
- Adjust model parameters like temperature, max tokens
- Provider-specific settings (reasoning effort for o3-mini, etc.)

### Supported Providers

**OpenAI**:
- GPT-4o, GPT-5, GPT-5-mini, GPT-5-nano
- GPT-4.1 (with web search), GPT-4.1-mini, GPT-4.1-nano
- o3, o3-pro, o3-mini (reasoning models)
- Legacy models: GPT-4, GPT-3.5-turbo

**Google Gemini**:
- Gemini-2.5-flash, Gemini-2.0-flash
- Gemini-1.5-pro, Gemini-1.5-flash

**Ollama** (Local models):
- Any model available in your local Ollama installation
- Automatic detection and configuration

## 🛠️ Development

### For Contributors

**Setup Development Environment**:
```bash
# Clone repository
git clone <repository-url>
cd omni_chat

# Setup virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
pytest -q

# Check code quality
black --check .
mypy . --ignore-missing-imports
```

**Project Structure**:
```
omni_chat/
├── app.py              # Main Flask application and routes
├── chat.py             # AI provider integrations
├── database.py         # SQLite database operations  
├── utils.py            # Shared utilities and configuration
├── email_service.py    # Email functionality
├── static/             # Frontend assets and configuration
├── templates/          # HTML templates and fragments
├── tests/              # Comprehensive test suite
└── docs/               # Documentation
```

**Key Development Commands**:
```bash
# Run application
python app.py

# Run tests (safe - no production impact)
pytest -q

# Format code
black .

# Type checking
mypy . --ignore-missing-imports

# Run with coverage
pytest --cov=. --cov-report=html
```

### Architecture

The application follows a modular, layered architecture:

- **Web Layer** (`app.py`): Flask routes and request handling
- **Logic Layer** (`chat.py`): AI provider abstractions and business logic
- **Data Layer** (`database.py`): SQLite operations and persistence
- **Utilities** (`utils.py`): Shared functions and configuration management
- **Frontend**: HTML templates with vanilla JavaScript for interactivity

**Design Patterns**:
- Application Factory (Flask)
- Provider Adapter (AI services)
- Data Access Object (Database)
- Configuration Manager (Environment)

See `docs/ARCHITECTURE.md` for detailed architecture documentation.

### Testing

The application includes a comprehensive test suite with complete isolation:

```bash
# Run all tests
pytest

# Run specific test category  
pytest tests/test_app.py      # API endpoint tests
pytest tests/test_chat.py     # Provider integration tests
pytest tests/test_database.py # Database operation tests

# Run with verbose output
pytest -v

# Generate coverage report
pytest --cov=. --cov-report=html
```

**Test Safety Features**:
- ✅ Complete isolation from production data
- ✅ No real API calls (all mocked)
- ✅ Temporary databases and config files
- ✅ Automatic cleanup after each test
- ✅ Can run offline without external dependencies

See `docs/TEST_SAFETY.md` for comprehensive test safety documentation.

## 🔒 Security & Privacy

- **Local Storage**: All chat data stored locally in SQLite
- **API Keys**: Stored in environment variables, never in source code
- **No Telemetry**: No data collection or external tracking
- **Input Validation**: All user inputs validated and sanitized
- **Test Isolation**: Tests never affect production data or make real API calls

## 📊 System Requirements

**Minimum**:
- Python 3.10+
- 100MB disk space
- 512MB RAM

**Recommended**:
- Python 3.12
- 1GB disk space (for chat history)
- 1GB RAM
- SSD storage for better performance

## 🐛 Troubleshooting

**Common Issues**:

1. **Missing API Key Error**
   - Add your API key via Settings or `.env` file
   - Ensure the key is valid and has sufficient credits

2. **Import/Module Errors**
   - Activate virtual environment: `source .venv/bin/activate`
   - Reinstall dependencies: `pip install -r requirements.txt`

3. **Database Locked**
   - Check for running Python processes: `ps aux | grep python`
   - Restart the application

4. **Tests Failing**
   - Ensure virtual environment is activated
   - Run `pip install -r requirements-dev.txt`
   - Check that production database is not being modified during tests

**Reset Application**:
```bash
# Reset chat history (WARNING: deletes all chats)
rm instance/omni_chat.db

# Reset configuration
rm .env
```

## 📚 Documentation

- `docs/ARCHITECTURE.md` - Detailed system architecture
- `docs/DEVELOPMENT.md` - Development setup and guidelines
- `docs/TEST_SAFETY.md` - Test isolation and safety mechanisms
- Inline code documentation with comprehensive docstrings
- Type hints throughout the codebase for better IDE support

## 🤝 Contributing

Contributions welcome! Please:

1. Read `docs/DEVELOPMENT.md` for setup instructions
2. Run the test suite: `pytest -q`
3. Follow code quality standards: `black --check . && mypy .`
4. Write tests for new features
5. Update documentation as needed

**Development Workflow**:
```bash
# Create feature branch
git checkout -b feature-name

# Make changes and test
pytest -q
black --check .

# Commit and push
git commit -m "feat: description of changes"
git push origin feature-name

# Open pull request
```

## 📄 License

MIT License - see `LICENSE` file for details.

## 🙏 Acknowledgments

- Built with [Flask](https://flask.palletsprojects.com/) web framework
- UI styled with [Tailwind CSS](https://tailwindcss.com/)
- Icons from [Google Material Icons](https://fonts.google.com/icons)
- Developed with assistance from GitHub Copilot

---

**Ready to start chatting with AI?** Follow the [Quick Start](#-quick-start) guide above!

For detailed documentation, see the `docs/` directory.
For development setup, see `docs/DEVELOPMENT.md`.
