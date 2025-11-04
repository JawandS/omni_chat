# Omni Chat

A lightweight, locally-hosted web chat interface that provides a unified way to interact with multiple AI providers. Switch between OpenAI, Google Gemini, Anthropic Claude, and Ollama models mid-conversation while maintaining your chat history in a local SQLite database.

## ✨ Features

### Core Capabilities
- **Multi-Provider Support**: OpenAI, Google Gemini, Anthropic Claude, and Ollama (local models)
- **Latest Models**: Claude Sonnet 4.5, GPT-4o, Gemini 2.5 Pro/Flash, and more
- **Model Switching**: Change AI providers and models within the same conversation
- **Local Storage**: All chats stored locally in SQLite - your data stays private
- **Project Organization**: Group related chats into projects for better organization

### Advanced AI Features
- **Real-time Streaming**: Live response streaming for all providers
- **Vision/Image Support**: Multi-modal conversations with image inputs
- **Extended Thinking**: Deep reasoning mode for Claude models
- **Prompt Caching**: Reduce costs with intelligent context caching (Claude)
- **JSON Mode**: Structured outputs for data extraction and APIs
- **Web Search**: Real-time web search with GPT-4.1 Live and Gemini Live

### Automation & Integration
- **Task Scheduling**: Schedule recurring AI tasks with email notifications
- **Email Integration**: Send task results via email with SMTP support
- **Favorites System**: Quick access to your preferred model configurations
- **Responsive UI**: Clean, modern interface that works on desktop and mobile

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
CLAUDE_API_KEY=sk-ant-your-claude-key-here
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
CLAUDE_API_KEY=sk-ant-your-claude-key-here
```

**Getting API Keys**:
- **OpenAI**: [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
- **Google Gemini**: [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
- **Anthropic Claude**: [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys)

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

**Anthropic Claude** (NEW):
- **Claude Sonnet 4.5**: Most intelligent model for complex tasks
- **Claude Haiku 4.5**: Fastest model with near-frontier intelligence
- **Claude Opus 4.1**: Exceptional for specialized reasoning
- Features: Extended thinking, prompt caching, vision support

**OpenAI**:
- **GPT-4o**: Most capable model, multimodal
- **GPT-4o-mini**: Fast and affordable
- **o1, o1-mini**: Advanced reasoning models
- **o3-mini**: Latest reasoning model
- Legacy: GPT-4-turbo, GPT-3.5-turbo

**Google Gemini**:
- **Gemini 2.5 Pro**: State-of-the-art reasoning and coding
- **Gemini 2.5 Flash**: Best price-performance ratio
- **Gemini 2.5 Flash-Lite**: Fastest with high throughput
- **Gemini 2.0 Flash**: Second generation workhorse
- **Gemini 2.5 Pro Live**: Real-time web search grounding

**Ollama** (Local models):
- Any model available in your local Ollama installation
- Automatic detection and configuration
- No API key required - runs entirely offline

## 🚀 Advanced Features

### Streaming Responses
Get real-time responses as the AI generates them for a more interactive experience. Supported by all providers (OpenAI, Claude, Gemini).

### Vision & Image Support
Send images along with your text prompts for multi-modal conversations:
- **Supported formats**: URLs, base64 data URIs
- **Use cases**: Image analysis, OCR, visual Q&A, diagram explanations
- **Providers**: All providers support vision-capable models

### Extended Thinking (Claude)
Enable deeper reasoning for complex problems:
```json
{
  "extended_thinking": true,
  "thinking_budget_tokens": 10000
}
```
- Allows Claude to "think" longer before responding
- Better for math, logic, coding, and complex analysis
- Configurable thinking budget (default: 10000 tokens)

### Prompt Caching (Claude)
Reduce API costs for conversations with large context:
```json
{
  "enable_caching": true
}
```
- Automatically caches recent message history
- Significantly reduces costs for long conversations
- Transparent - no changes to your workflow needed

### JSON Mode
Get structured, predictable responses for data extraction:
```json
{
  "json_mode": true
}
```
- Forces AI to respond with valid JSON only
- Perfect for API integrations and data processing
- Supported by OpenAI and Claude

### Web Search Integration
Access real-time information with search-enabled models:
- **GPT-4.1 Live**: OpenAI's web search integration
- **Gemini 2.5 Pro Live**: Google's search grounding
- Automatically searches and cites sources
- Perfect for current events, latest data, and research

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
