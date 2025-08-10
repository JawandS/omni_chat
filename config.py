import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", os.urandom(24))
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///omni_chat.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "")  # Fernet key base64 string

    # Provider defaults
    OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
    ANTHROPIC_API_BASE = os.getenv("ANTHROPIC_API_BASE", "https://api.anthropic.com")
    GEMINI_API_BASE = os.getenv("GEMINI_API_BASE", "https://generativelanguage.googleapis.com")
