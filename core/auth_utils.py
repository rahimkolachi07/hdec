"""
File-based user store. No database required.
Users saved to: <project_root>/users.json
Default admin created automatically on first run.
"""
import json, hashlib, os
from pathlib import Path

USERS_FILE = Path(__file__).resolve().parent.parent / 'users.json'


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def _load() -> dict:
    if not USERS_FILE.exists():
        default = {
            "admin": {
                "password": _hash("admin123"),
                "role": "admin",
                "name": "Administrator"
            }
        }
        _save(default)
        return default
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data: dict):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def authenticate(username: str, password: str):
    """Returns {'username', 'role', 'name'} dict or None."""
    if not username or not password:
        return None
    users = _load()
    key = username.strip().lower()
    user = users.get(key)
    if user and user.get('password') == _hash(password):
        return {'username': key, 'role': user['role'], 'name': user['name']}
    return None


def get_all_users():
    users = _load()
    return [
        {'username': u, 'role': d['role'], 'name': d['name']}
        for u, d in users.items()
    ]


def create_user(username: str, password: str, name: str, role: str = 'viewer'):
    if not username or not password or not name:
        return False, 'All fields are required'
    if len(password) < 4:
        return False, 'Password must be at least 4 characters'
    users = _load()
    key = username.strip().lower()
    if key in users:
        return False, f'Username "{key}" already exists'
    users[key] = {'password': _hash(password), 'role': role, 'name': name.strip()}
    _save(users)
    return True, 'User created successfully'


def delete_user(username: str):
    users = _load()
    key = username.strip().lower()
    if key == 'admin':
        return False, 'Cannot delete the main admin account'
    if key not in users:
        return False, 'User not found'
    del users[key]
    _save(users)
    return True, f'User "{key}" deleted'


def change_password(username: str, new_password: str):
    if not new_password or len(new_password) < 4:
        return False, 'Password must be at least 4 characters'
    users = _load()
    key = username.strip().lower()
    if key not in users:
        return False, 'User not found'
    users[key]['password'] = _hash(new_password)
    _save(users)
    return True, 'Password updated successfully'
