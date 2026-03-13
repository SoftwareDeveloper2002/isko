from fastapi import APIRouter, Header, status, HTTPException, Response, UploadFile, File
from models import ProjectResponse, ProjectCreateRequest, ProjectUpdateRequest, ProjectApproveRequest
from database import get_conn
from project import find_project_by_id
from utility import get_current_user_from_auth_header
from project import normalize_project, row_to_project
from config import UPLOADS_DIR
from secrets import token_urlsafe

router = APIRouter(prefix="/projects", tags=["projects"])

@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreateRequest, authorization: str | None = Header(default=None)) -> ProjectResponse:
    user = get_current_user_from_auth_header(authorization)

    if user.get("role") != "student":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only students can post projects")

    project_id = token_urlsafe(10)

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO projects (id, project_type, title, description, budget, owner_email, approved_developer_email)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                payload.project_type,
                payload.title.strip(),
                payload.description.strip(),
                round(float(payload.budget), 2),
                user["email"],
                None,
            ),
        )
        row = conn.execute(
            """
            SELECT id, project_type, title, description, budget, owner_email, approved_developer_email, created_at
            FROM projects WHERE id = ?
            """,
            (project_id,)
        ).fetchone()
        project = row_to_project(conn, row)

    return ProjectResponse(**project)

@router.get("", response_model=list[ProjectResponse])
def list_projects(authorization: str | None = Header(default=None)) -> list[ProjectResponse]:
    user = get_current_user_from_auth_header(authorization)

    with get_conn() as conn:
        if user.get("role") == "student":
            rows = conn.execute(
                """
                SELECT id, project_type, title, description, budget, owner_email, approved_developer_email, created_at
                FROM projects
                WHERE owner_email = ?
                ORDER BY created_at DESC
                """,
                (user["email"],),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, project_type, title, description, budget, owner_email, approved_developer_email, created_at
                FROM projects
                ORDER BY created_at DESC
                """
            ).fetchall()

        projects = [row_to_project(conn, row) for row in rows]

    return [ProjectResponse(**project) for project in projects]

@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, authorization: str | None = Header(default=None)) -> ProjectResponse:
    user = get_current_user_from_auth_header(authorization)
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT id, project_type, title, description, budget, owner_email, approved_developer_email, created_at
            FROM projects WHERE id = ?
            """,
            (project_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Project not found")
        project = row_to_project(conn, row)
    return ProjectResponse(**project)

@router.post("/{project_id}/apply", response_model=ProjectResponse)
def apply_to_project(project_id: str, authorization: str | None = Header(default=None)) -> ProjectResponse:
    user = get_current_user_from_auth_header(authorization)
    if user.get("role") != "developer":
        raise HTTPException(status_code=403, detail="Only developers can apply to projects")
    with get_conn() as conn:
        project_row = conn.execute(
            """
            SELECT id FROM projects WHERE id = ?
            """,
            (project_id,)
        ).fetchone()
        if not project_row:
            raise HTTPException(status_code=404, detail="Project not found")
        # Check if already applied
        existing = conn.execute(
            """
            SELECT developer_email FROM project_applications WHERE project_id = ? AND developer_email = ?
            """,
            (project_id, user["email"])
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="Already applied to this project")
        conn.execute(
            """
            INSERT INTO project_applications (project_id, developer_email, status, created_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (project_id, user["email"], "pending")
        )
        # Return updated project
        row = conn.execute(
            """
            SELECT id, project_type, title, description, budget, owner_email, approved_developer_email, created_at
            FROM projects WHERE id = ?
            """,
            (project_id,)
        ).fetchone()
        project = row_to_project(conn, row)
    return ProjectResponse(**project)

@router.post("/{project_id}/approve", response_model=ProjectResponse)
def approve_project_application(project_id: str, payload: ProjectApproveRequest, authorization: str | None = Header(default=None)) -> ProjectResponse:
    user = get_current_user_from_auth_header(authorization)
    if user.get("role") != "student":
        raise HTTPException(status_code=403, detail="Only students can approve developers")
    with get_conn() as conn:
        # Check project ownership
        row = conn.execute(
            """
            SELECT owner_email FROM projects WHERE id = ?
            """,
            (project_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Project not found")
        if row["owner_email"] != user["email"]:
            raise HTTPException(status_code=403, detail="Not authorized to approve for this project")
        # Approve developer
        conn.execute(
            """
            UPDATE project_applications SET status = 'approved' WHERE project_id = ? AND developer_email = ?
            """,
            (project_id, payload.developer_email)
        )
        conn.execute(
            """
            UPDATE projects SET approved_developer_email = ? WHERE id = ?
            """,
            (payload.developer_email, project_id)
        )
        # Return updated project
        project_row = conn.execute(
            """
            SELECT id, project_type, title, description, budget, owner_email, approved_developer_email, created_at
            FROM projects WHERE id = ?
            """,
            (project_id,)
        ).fetchone()
        project = row_to_project(conn, project_row)
    return ProjectResponse(**project)

@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(project_id: str, payload: ProjectUpdateRequest, authorization: str | None = Header(default=None)) -> ProjectResponse:
    # ...existing code from main.py...
    pass

@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response, response_model=None)
def delete_project(project_id: str, authorization: str | None = Header(default=None)) -> Response:
    user = get_current_user_from_auth_header(authorization)
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT owner_email FROM projects WHERE id = ?
            """,
            (project_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Project not found")
        if user.get("role") != "student" or row["owner_email"] != user["email"]:
            raise HTTPException(status_code=403, detail="Not authorized to delete this project")
        conn.execute(
            """
            DELETE FROM projects WHERE id = ?
            """,
            (project_id,)
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.post("/{project_id}/attachments", response_model=ProjectResponse)
def upload_project_attachment(project_id: str, attachment: UploadFile = File(...), authorization: str | None = Header(default=None)) -> ProjectResponse:
    # ...existing code from main.py...
    pass
