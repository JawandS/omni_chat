from flask import Blueprint, render_template, request, redirect, url_for, flash
from ..db import db
from ..models import ApiKey
from ..utils.crypto import encrypt_value

settings_bp = Blueprint('settings', __name__)


@settings_bp.route('/', methods=['GET'])
def settings_index():
    keys = ApiKey.query.order_by(ApiKey.provider.asc(), ApiKey.created_at.desc()).all()
    return render_template('settings.html', keys=keys)


@settings_bp.route('/save', methods=['POST'])
def save_key():
    provider = request.form.get('provider')
    api_key = request.form.get('api_key')
    if not provider or not api_key:
        flash('Provider and API key are required', 'error')
        return redirect(url_for('settings.settings_index'))
    token = encrypt_value(api_key)
    row = ApiKey(provider=provider, key_encrypted=token)
    db.session.add(row)
    db.session.commit()
    flash('API key saved', 'success')
    return redirect(url_for('settings.settings_index'))


@settings_bp.route('/delete/<int:key_id>', methods=['POST'])
def delete_key(key_id):
    row = ApiKey.query.get_or_404(key_id)
    db.session.delete(row)
    db.session.commit()
    flash('API key deleted', 'success')
    return redirect(url_for('settings.settings_index'))
