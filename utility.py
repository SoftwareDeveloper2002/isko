import sqlite3
from hashlib import sha256
from fastapi import HTTPException, status
from database import get_conn
import re

def hash_password(password: str) -> str:
    return sha256(password.encode("utf-8")).hexdigest()

def is_valid_hex_color(color: str) -> bool:
    """Check if a string is a valid hex color (#RRGGBB or #RGB)."""
    if not isinstance(color, str):
        return False
    pattern = r'^#(?:[0-9a-fA-F]{3}){1,2}$'
    return re.match(pattern, color) is not None

def find_user_by_email(email: str) -> dict | None:
    target = email.strip().lower()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT email, name, password_hash, role FROM users WHERE email = ?",
            (target,),
        ).fetchone()

        if not row:
            return None

        return {
            "email": row["email"],
            "name": row["name"],
            "password_hash": row["password_hash"],
            "role": row["role"],
        }

def get_current_user_from_auth_header(authorization: str | None) -> dict:
    from main import parse_bearer_token
    token = parse_bearer_token(authorization)
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT u.email, u.name, u.password_hash, u.role
            FROM sessions s
            JOIN users u ON u.email = s.email
            WHERE s.token = ?
            """,
            (token,),
        ).fetchone()

        if not row:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

        return {
            "email": row["email"],
            "name": row["name"],
            "password_hash": row["password_hash"],
            "role": row["role"],
        }
