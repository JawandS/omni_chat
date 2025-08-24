# Omni Chat

A simple and lightweight chat interface with a model selector you control (uses API calls). Lets you switch models / providers mid chat. Meant to run locally, uses SQLite to store history. 

## Quick start

Prereqs: Python 3.10+

```bash
# 1) (optional) create a virtual environment
python -m venv .venv
source .venv/bin/activate

# 2) install dependencies
pip install -r requirements.txt

# 3) run the app
python app.py
# open http://127.0.0.1:5000

# 4) configure API key (settings icon or .env file)
OPENAI_API_KEY=sk-...your-openai-key...
GEMINI_API_KEY=...your-gemini-key...
```

## Email Setup (Optional)

The application supports sending task results via email. To configure email functionality:

### 1. Configure SMTP Settings

Click the settings icon (⚙️) in the application and go to the **Email** tab, or add the following to your `.env` file:

```bash
# Email Configuration
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com    # Usually same as FROM_EMAIL
SMTP_PASSWORD=your-app-password
SMTP_USE_TLS=true
FROM_EMAIL=your-email@gmail.com       # Usually same as SMTP_USERNAME
```

**Note:** For most email providers (Gmail, Yahoo, Outlook), `SMTP_USERNAME` and `FROM_EMAIL` are the same - your email address. They're separate fields to support corporate email servers where authentication username might differ from the sending address.

### 2. Gmail Setup (Recommended)

For Gmail, you'll need to use an App Password instead of your regular password:

1. Enable 2-Factor Authentication on your Google account
2. Go to [Google App Passwords](https://myaccount.google.com/apppasswords)
3. Generate a new App Password for "Mail"
4. Use this App Password in the `SMTP_PASSWORD` field

### 3. Other Email Providers

Common SMTP settings for other providers:

**Outlook/Hotmail:**
- SMTP Server: `smtp-mail.outlook.com`
- Port: `587`
- TLS: `true`

**Yahoo:**
- SMTP Server: `smtp.mail.yahoo.com`
- Port: `587` or `465`
- TLS: `true`

### 4. Test Your Configuration

After configuring SMTP settings:
1. Go to Settings → Email tab
2. Enter a test email address
3. Click "Test" to verify your configuration
4. You should receive a test email if everything is set up correctly

### 5. Using Email in Tasks

When creating scheduled tasks:
1. Set "Output Destination" to "Email"
2. Enter the recipient email address
3. When the task executes, results will be sent to the specified email
4. Email subject format: `{task_name} - {timestamp}`

## Provider and model support
- Currently supporting OpenAI/Gemini
- You can update `static/providers.json` for other models (might need to customize) `chat.py` for a different API call

# Dev
## Structure
- `app.py`: main file with routes
- `chat.py`: call various APIs
- `database.py`: integrate with SQLite

## Run tests

```bash
pytest -q
```

Notes:
- Tests use a temp SQLite DB and monkeypatch provider calls – no real network calls.
- The main DB lives at `instance/omni_chat.db` (created on first run).

## Troubleshooting

- Missing API key: The message shows an inline error and may auto‑open Settings. Add your key and retry.
- OpenAI reasoning models (o3*): Make sure your account has access; if calls fail, try a standard model to validate setup.
- Reset the database: Stop the app and delete `instance/omni_chat.db` (you’ll lose chats).

## License

MIT License. See `LICENSE.md` if present; otherwise the project is intended to be used under the MIT terms.

## Contributing

Contributions are welcome! Feel free to open issues or pull requests for bugs, features, or docs. Please run the test suite (`pytest -q`) before submitting and update as needed.

## AI
Developed with the help of GitHub Copilot (GPT-5)
