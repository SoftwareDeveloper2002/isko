import sqlite3
from database import get_conn
from wallet import get_wallet_transactions, get_wallet_balance, create_wallet_transaction
from models import ProjectCreateRequest, ProjectUpdateRequest, ProjectResponse, ProjectApproveRequest
from secrets import token_urlsafe
from typing import Literal
from project_utils import get_project_applications, get_project_attachments

# Project-related database functions

def find_project_by_id(conn, project_id: str) -> dict | None:
    row = conn.execute(
        """
        SELECT id, project_type, title, description, budget, owner_email, approved_developer_email
        FROM projects
        WHERE id = ?
        """,
        (project_id,),
    ).fetchone()

    if not row:
        return None

    # You may need to add attachments/applications logic here
    return dict(row)


def normalize_project(project: dict) -> dict:
    if "applications" not in project or not isinstance(project.get("applications"), list):
        project["applications"] = []

    if "attachments" not in project or not isinstance(project.get("attachments"), list):
        project["attachments"] = []

    if "approved_developer_email" not in project:
        project["approved_developer_email"] = None

    return project

def row_to_project(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    project = {
        "id": row["id"],
        "project_type": row["project_type"],
        "title": row["title"],
        "description": row["description"],
        "budget": float(row["budget"]),
        "owner_email": row["owner_email"],
        "approved_developer_email": row["approved_developer_email"],
        "created_at": row["created_at"],
        "applications": get_project_applications(conn, row["id"]),
        "attachments": get_project_attachments(conn, row["id"]),
    }
    return normalize_project(project)
