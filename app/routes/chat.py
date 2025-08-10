from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from ..db import db
from ..models import ChatSession, Message, ApiKey
from ..utils.crypto import decrypt_value
from ..providers import PROVIDERS
import asyncio

chat_bp = Blueprint('chat', __name__)


@chat_bp.route('/')
def index():
    sessions = ChatSession.query.order_by(ChatSession.created_at.desc()).all()
    return render_template('chat.html', sessions=sessions)


@chat_bp.route('/chat/<int:session_id>')
def chat_session(session_id):
    session = ChatSession.query.get_or_404(session_id)
    messages = Message.query.filter_by(session_id=session.id).order_by(Message.created_at.asc()).all()
    sessions = ChatSession.query.order_by(ChatSession.created_at.desc()).all()
    return render_template('chat.html', session=session, messages=messages, sessions=sessions)


@chat_bp.route('/chat/new', methods=['POST'])
def new_chat():
    provider = request.form.get('provider', 'openai')
    model = request.form.get('model', 'gpt-4o-mini')
    title = request.form.get('title', 'New Chat')
    session = ChatSession(provider=provider, model=model, title=title)
    db.session.add(session)
    db.session.commit()
    return redirect(url_for('chat.chat_session', session_id=session.id))


@chat_bp.route('/chat/<int:session_id>/message', methods=['POST'])
def send_message(session_id):
    session = ChatSession.query.get_or_404(session_id)
    content = request.form.get('content', '').strip()
    if not content:
        return redirect(url_for('chat.chat_session', session_id=session.id))

    user_msg = Message(session_id=session.id, role='user', content=content)
    db.session.add(user_msg)
    db.session.commit()

    # Fetch API key for provider
    api_key_row = ApiKey.query.filter_by(provider=session.provider).order_by(ApiKey.created_at.desc()).first()
    if not api_key_row:
        assistant_msg = Message(session_id=session.id, role='assistant', content=f"No API key configured for {session.provider}. Go to Settings.")
        db.session.add(assistant_msg)
        db.session.commit()
        return redirect(url_for('chat.chat_session', session_id=session.id))

    api_key = None
    try:
        api_key = decrypt_value(api_key_row.key_encrypted)
    except Exception as e:
        api_key = None

    if not api_key:
        assistant_msg = Message(session_id=session.id, role='assistant', content="API key could not be decrypted. Check settings.")
        db.session.add(assistant_msg)
        db.session.commit()
        return redirect(url_for('chat.chat_session', session_id=session.id))

    # Build provider messages
    msgs = [{'role': m.role, 'content': m.content} for m in Message.query.filter_by(session_id=session.id).order_by(Message.created_at.asc()).all()]

    provider = PROVIDERS.get(session.provider)
    if not provider:
        assistant_msg = Message(session_id=session.id, role='assistant', content=f"Provider '{session.provider}' not found.")
        db.session.add(assistant_msg)
        db.session.commit()
        return redirect(url_for('chat.chat_session', session_id=session.id))

    async def call_model():
        try:
            reply = await provider.chat(msgs, model=session.model, api_key=api_key)
        except Exception as e:
            reply = f"Error: {e}"
        return reply

    reply_text = asyncio.run(call_model())

    assistant_msg = Message(session_id=session.id, role='assistant', content=reply_text)
    db.session.add(assistant_msg)
    db.session.commit()

    return redirect(url_for('chat.chat_session', session_id=session.id))


@chat_bp.route('/chat/<int:session_id>/meta', methods=['POST'])
def update_session_meta(session_id):
    session = ChatSession.query.get_or_404(session_id)
    provider = request.form.get('provider')
    model = request.form.get('model')
    title = request.form.get('title')
    if provider:
        session.provider = provider
    if model:
        session.model = model
    if title:
        session.title = title
    db.session.commit()
    return redirect(url_for('chat.chat_session', session_id=session.id))


@chat_bp.route('/chat/<int:session_id>/delete', methods=['POST'])
def delete_session(session_id):
    session = ChatSession.query.get_or_404(session_id)
    Message.query.filter_by(session_id=session.id).delete()
    db.session.delete(session)
    db.session.commit()
    return redirect(url_for('chat.index'))
