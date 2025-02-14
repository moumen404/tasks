

from flask import Blueprint, render_template, session, redirect, url_for, jsonify
from app import load_data

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.before_request
def check_admin():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))
    data = load_data()
    user = next((u for u in data['users'] if u['id'] == user_id), None)
    if not user or not user.get('is_admin', False):
        return redirect(url_for('index'))

@admin_bp.route('/dashboard')
def dashboard():
    return render_template('admin_dashboard.html')

@admin_bp.route('/users')
def get_users():
    data = load_data()
    users = []
    for user in data.get('users', []):
        sanitized = {
            'id': user['id'],
            'name': user['name'],
            'email': user['email'],
            'goals': user.get('goals', []),
            'is_admin': user.get('is_admin', False)
        }
        users.append(sanitized)
    return jsonify(users)

app.register_blueprint(admin_bp)
