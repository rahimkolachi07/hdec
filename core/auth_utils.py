"""
File-based user store. No database required.
Users saved to: <project_root>/users.json
Default admin created automatically on first run.

Roles:
  admin               — full system access, upload templates
  maintenance_engineer — apply for permits (receiver), tick checklists, sign
  operation_engineer  — issue permits
  hse_engineer        — sign permits, allocate permit/isolation numbers
  technician          — upload before/after photos
  viewer              — read-only access

Permissions (per module):
  'edit'  — full create / modify / delete
  'view'  — read-only
  'none'  — no access (hidden + blocked)
"""
import json, hashlib, os
from pathlib import Path

USERS_FILE = Path(__file__).resolve().parent.parent / 'users.json'

VALID_ROLES = [
    'admin',
    'maintenance_engineer',
    'operation_engineer',
    'hse_engineer',
    'technician',
    'viewer',
]

ROLE_LABELS = {
    'admin':               '👑 Admin',
    'maintenance_engineer':'🔧 Maintenance Engineer',
    'operation_engineer':  '⚙️ Operation Engineer',
    'hse_engineer':        '🦺 HSE Engineer',
    'technician':          '🛠️ Technician',
    'viewer':              '👁 Viewer',
}

# All modules with display labels
MODULES = {
    'activities':   '📋 CMMS Activities',
    'permits':      '🔐 Work Permits (PTW)',
    'handover':     '📝 Shift Handover',
    'manpower':     '👷 Manpower',
    'tracing':      '🗂 Tracing Sheets',
    'annual_plan':  '📅 Annual Plan',
    'documents':    '📄 Documents',
    'daily_report': '📊 Daily Report',
}

# Default permissions per role
DEFAULT_PERMISSIONS = {
    'admin': {m: 'edit' for m in MODULES},
    'maintenance_engineer': {
        'activities':   'edit',
        'permits':      'edit',
        'handover':     'edit',
        'manpower':     'view',
        'tracing':      'view',
        'annual_plan':  'view',
        'documents':    'view',
        'daily_report': 'view',
    },
    'operation_engineer': {
        'activities':   'view',
        'permits':      'edit',
        'handover':     'view',
        'manpower':     'view',
        'tracing':      'view',
        'annual_plan':  'view',
        'documents':    'view',
        'daily_report': 'view',
    },
    'hse_engineer': {
        'activities':   'view',
        'permits':      'edit',
        'handover':     'view',
        'manpower':     'view',
        'tracing':      'view',
        'annual_plan':  'view',
        'documents':    'view',
        'daily_report': 'view',
    },
    'technician': {
        'activities':   'edit',
        'permits':      'view',
        'handover':     'none',
        'manpower':     'none',
        'tracing':      'none',
        'annual_plan':  'none',
        'documents':    'view',
        'daily_report': 'none',
    },
    'viewer': {m: 'view' for m in MODULES},
}


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def _load() -> dict:
    if not USERS_FILE.exists():
        default = {
            "admin": {
                "password": _hash("admin123"),
                "role": "admin",
                "name": "Administrator",
                "email": "",
                "permissions": DEFAULT_PERMISSIONS['admin'],
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


def _get_permissions(user_data: dict) -> dict:
    """Return permissions dict, falling back to role defaults for missing modules."""
    role = user_data.get('role', 'viewer')
    defaults = DEFAULT_PERMISSIONS.get(role, {m: 'view' for m in MODULES})
    saved = user_data.get('permissions', {})
    # Merge: saved values override defaults (so old users without permissions get defaults)
    merged = dict(defaults)
    merged.update({k: v for k, v in saved.items() if k in MODULES})
    return merged


def authenticate(username: str, password: str):
    """Returns {'username', 'role', 'name', 'email', 'permissions'} dict or None."""
    if not username or not password:
        return None
    users = _load()
    key = username.strip().lower()
    user = users.get(key)
    if user and user.get('password') == _hash(password):
        return {
            'username': key,
            'role': user['role'],
            'name': user['name'],
            'email': user.get('email', ''),
            'permissions': _get_permissions(user),
        }
    return None


def get_all_users():
    users = _load()
    return [
        {
            'username': u,
            'role': d['role'],
            'name': d['name'],
            'email': d.get('email', ''),
            'role_label': ROLE_LABELS.get(d['role'], d['role']),
            'permissions': _get_permissions(d),
        }
        for u, d in users.items()
    ]


def get_users_by_role(role: str):
    """Return list of users with a specific role."""
    return [u for u in get_all_users() if u['role'] == role]


def get_user_detail(username: str):
    """Return full user detail including email and permissions."""
    users = _load()
    key = username.strip().lower()
    d = users.get(key)
    if not d:
        return None
    return {
        'username': key,
        'role': d['role'],
        'name': d['name'],
        'email': d.get('email', ''),
        'role_label': ROLE_LABELS.get(d['role'], d['role']),
        'permissions': _get_permissions(d),
    }


def create_user(username: str, password: str, name: str, role: str = 'viewer',
                email: str = '', permissions: dict = None):
    if not username or not password or not name:
        return False, 'All fields are required'
    if len(password) < 4:
        return False, 'Password must be at least 4 characters'
    if role not in VALID_ROLES:
        return False, f'Invalid role: {role}'
    users = _load()
    key = username.strip().lower()
    if key in users:
        return False, f'Username "{key}" already exists'

    # Build permissions: use provided dict if valid, else role defaults
    if permissions and isinstance(permissions, dict):
        perms = {m: permissions.get(m, DEFAULT_PERMISSIONS.get(role, {}).get(m, 'view'))
                 for m in MODULES}
    else:
        perms = DEFAULT_PERMISSIONS.get(role, {m: 'view' for m in MODULES})

    users[key] = {
        'password': _hash(password),
        'role': role,
        'name': name.strip(),
        'email': email.strip(),
        'permissions': perms,
    }
    _save(users)
    return True, 'User created successfully'


def update_user_permissions(username: str, permissions: dict):
    """Update module permissions for a user."""
    users = _load()
    key = username.strip().lower()
    if key not in users:
        return False, 'User not found'
    # Validate and sanitise
    clean = {}
    for module in MODULES:
        val = permissions.get(module, 'view')
        if val not in ('edit', 'view', 'none'):
            val = 'view'
        clean[module] = val
    users[key]['permissions'] = clean
    _save(users)
    return True, 'Permissions updated'


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


def update_user_email(username: str, email: str):
    users = _load()
    key = username.strip().lower()
    if key not in users:
        return False, 'User not found'
    users[key]['email'] = email.strip()
    _save(users)
    return True, 'Email updated'


def has_permission(user: dict, module: str, level: str = 'view') -> bool:
    """
    Check if user has at least `level` access to `module`.
    level='view'  → True if permissions[module] in ('view','edit')
    level='edit'  → True if permissions[module] == 'edit'
    Admin role always returns True.
    """
    if user.get('role') == 'admin':
        return True
    perms = user.get('permissions', {})
    access = perms.get(module, 'none')
    if level == 'edit':
        return access == 'edit'
    if level == 'view':
        return access in ('view', 'edit')
    return False
