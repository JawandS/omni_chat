from datetime import datetime
from .db import db


class ApiKey(db.Model):
    __tablename__ = 'api_keys'
    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(50), nullable=False)  # 'openai', 'anthropic', 'gemini'
    key_encrypted = db.Column(db.LargeBinary, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ChatSession(db.Model):
    __tablename__ = 'chat_sessions'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), default='New Chat')
    provider = db.Column(db.String(50), default='openai')
    model = db.Column(db.String(200), default='gpt-4o-mini')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('chat_sessions.id'), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'user' or 'assistant' or 'system'
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    session = db.relationship('ChatSession', backref=db.backref('messages', lazy=True, order_by="Message.created_at"))


def init_db():
    db.create_all()
