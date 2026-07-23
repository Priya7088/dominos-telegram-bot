"""
Session Store — JSON-based storage for Domino's India sessions.
Each Telegram user can have multiple Domino's accounts (phone numbers).
"""
import json
import os
import time
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

from config import SESSION_DB_PATH, SECRET_KEY


def _derive_fernet_key(secret: str) -> bytes:
    """Derive a Fernet-compatible key from the secret key."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"dominos_bot_salt_2024",
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(secret.encode()))
    return key


_fernet = Fernet(_derive_fernet_key(SECRET_KEY))


class SessionStore:
    def __init__(self, db_path: str = SESSION_DB_PATH):
        self.db_path = db_path
        self._ensure_db()

    def _ensure_db(self):
        """Create sessions.json if it doesn't exist."""
        if not os.path.exists(self.db_path):
            with open(self.db_path, "w") as f:
                json.dump({}, f)

    def _load(self) -> dict:
        with open(self.db_path, "r") as f:
            return json.load(f)

    def _save(self, data: dict):
        with open(self.db_path, "w") as f:
            json.dump(data, f, indent=2)

    def _encrypt_cookies(self, cookies: list) -> str:
        """Encrypt cookies before storing."""
        data = json.dumps(cookies)
        return _fernet.encrypt(data.encode()).decode()

    def _decrypt_cookies(self, encrypted: str) -> list:
        """Decrypt stored cookies."""
        try:
            data = _fernet.decrypt(encrypted.encode()).decode()
            return json.loads(data)
        except Exception:
            return []

    # ---------- Public API ----------

    def get_user_accounts(self, telegram_id: int) -> dict:
        """
        Return dict of {phone_number: encrypted_cookies, ...}
        for a given Telegram user.
        """
        db = self._load()
        return db.get(str(telegram_id), {})

    def get_session_cookies(
        self, telegram_id: int, phone_number: str
    ) -> list:
        """Return decrypted cookies for a specific account."""
        accounts = self.get_user_accounts(telegram_id)
        encrypted = accounts.get(phone_number)
        if encrypted:
            cookies = self._decrypt_cookies(encrypted)
            # Check expiry
            if cookies and isinstance(cookies, list):
                return cookies
        return []

    def save_session(
        self,
        telegram_id: int,
        phone_number: str,
        cookies: list,
        user_info: dict = None,
    ):
        """Save/update cookies for a phone number."""
        db = self._load()
        tid = str(telegram_id)
        if tid not in db:
            db[tid] = {}
        db[tid][phone_number] = {
            "cookies": self._encrypt_cookies(cookies),
            "user_info": user_info or {},
            "saved_at": time.time(),
        }
        self._save(db)

    def remove_account(self, telegram_id: int, phone_number: str):
        """Remove a specific account."""
        db = self._load()
        tid = str(telegram_id)
        if tid in db and phone_number in db[tid]:
            del db[tid][phone_number]
            self._save(db)

    def get_all_phone_numbers(self, telegram_id: int) -> list:
        """Return list of saved phone numbers for a user."""
        accounts = self.get_user_accounts(telegram_id)
        return list(accounts.keys())

    def get_active_account(self, telegram_id: int) -> str | None:
        """
        Return the currently 'active' phone number for a user.
        """
        accounts = self.get_user_accounts(telegram_id)
        if not accounts:
            return None
        # Return first account as default active
        return list(accounts.keys())[0]

    def set_active_account(self, telegram_id: int, phone_number: str):
        """This is handled by re-ordering the dict — move to front."""
        db = self._load()
        tid = str(telegram_id)
        if tid in db and phone_number in db[tid]:
            # Move to front by re-inserting
            item = db[tid].pop(phone_number)
            new_dict = {phone_number: item}
            new_dict.update(db[tid])
            db[tid] = new_dict
            self._save(db)


# Singleton instance
session_store = SessionStore()
