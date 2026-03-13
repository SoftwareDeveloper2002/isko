# dependencies.py

from fastapi import Header
import sqlite3
from pathlib import Path

UPLOADS_DIR = Path("uploads")

def get_conn():
    return sqlite3.connect("database.db")

def get_current_user_from_auth_header(authorization: str = Header(None)):
    if not authorization:
        return None
    return authorization
