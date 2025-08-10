from flask import Flask
from .db import db
from .models import init_db
from .routes.chat import chat_bp
from .routes.settings import settings_bp
from config import Config


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    with app.app_context():
        init_db()

    app.register_blueprint(chat_bp)
    app.register_blueprint(settings_bp, url_prefix='/settings')

    return app
