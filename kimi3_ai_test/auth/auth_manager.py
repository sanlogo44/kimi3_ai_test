import json, hashlib, secrets
from pathlib import Path
from typing import Optional, Dict

class AuthManager:
    def __init__(self, db_path="auth/users.json"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = self._load_db()
        self._ensure_default_admin()

    def _load_db(self):
        if not self.db_path.exists(): return {"users":{}, "first_login":True}
        with open(self.db_path,'r',encoding='utf-8') as f: return json.load(f)

    def _save_db(self):
        with open(self.db_path,'w',encoding='utf-8') as f: json.dump(self._db, f, indent=2)

    def _hash(self, password: str, salt: Optional[str]=None):
        salt = salt or secrets.token_hex(16)
        return salt, hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000).hex()

    def _ensure_default_admin(self):
        if "admin" not in self._db["users"]:
            salt, pwdhash = self._hash("1234")
            self._db["users"]["admin"] = {"username":"Admin","password_hash":pwdhash,"salt":salt,"role":"admin","force_password_change":True}
            self._save_db()

    def authenticate(self, username: str, password: str) -> Optional[Dict]:
        user = self._db["users"].get(username.lower())
        if not user: return None
        salt, test_hash = self._hash(password, user["salt"])
        if test_hash == user["password_hash"]:
            return {"username":user["username"],"role":user["role"],"force_password_change":user.get("force_password_change",False)}
        return None

    def change_credentials(self, old_user: str, new_username: str, new_password: str) -> bool:
        old_key = old_user.lower()
        if old_key not in self._db["users"]: return False
        data = self._db["users"].pop(old_key)
        salt, pwdhash = self._hash(new_password)
        data.update({"username":new_username,"password_hash":pwdhash,"salt":salt,"force_password_change":False})
        self._db["users"][new_username.lower()] = data
        self._save_db(); return True

    def is_admin(self, username: str) -> bool:
        return self._db["users"].get(username.lower(),{}).get("role")=="admin"

    def is_first_login(self): return self._db.get("first_login",True)
    def mark_first_login_done(self): self._db["first_login"]=False; self._save_db()