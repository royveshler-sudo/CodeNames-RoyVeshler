_author_ = 'Roy'

import hashlib
import json
import os
import threading


USERS_FILE = "data/users.json"

_lock = threading.Lock()


def _hash_password(password, salt):
    h = hashlib.sha256(salt + password.encode("utf-8")).hexdigest()
    return salt.hex() + ":" + h


def _verify_password(password, stored):
    try:
        salt_hex, _ = stored.split(":", 1)
        salt = bytes.fromhex(salt_hex)
    except (ValueError, TypeError):
        return False
    return _hash_password(password, salt) == stored


def _load() :
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(users):
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)


class UserStore:
    def __init__(self):
        with _lock:
            self._users = _load()

    def signup(self, username, password):
        username = (username or "").strip()
        if not username or not password:
            return False, "Username and password are required"
        if len(username) > 20 or " " in username:
            return False, "Username must be one word, up to 20 characters"
        if len(password) < 4:
            return False, "Password must be at least 4 characters"

        with _lock:
            if username in self._users:
                return False, "Username is already taken"
            salt = os.urandom(16)
            self._users[username] = _hash_password(password, salt)
            _save(self._users)
        return True, None

    def login(self, username, password):
        username = (username or "").strip()
        with _lock:
            stored = self._users.get(username)
        if stored is None or not _verify_password(password, stored):
            return False, "Incorrect username or password"
        return True, None
