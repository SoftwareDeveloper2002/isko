from __future__ import annotations
from fastapi import APIRouter, File, Header, HTTPException, UploadFile, status
from pathlib import Path
from dependencies import get_current_user_from_auth_header, get_conn, UPLOADS_DIR

router = APIRouter(prefix="/developer", tags=["developer"])

@router.post("/verify")
def developer_verify(
    authorization: str | None = Header(default=None),
    id: UploadFile = File(...),
    resume: UploadFile = File(...)
):
    user = get_current_user_from_auth_header(authorization)
    if user.get("role") != "developer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only developers can verify.")

    # Save files
    id_filename = f"{user['email']}_id_{id.filename}"
    resume_filename = f"{user['email']}_resume_{resume.filename}"
    id_path = UPLOADS_DIR / id_filename
    resume_path = UPLOADS_DIR / resume_filename
    with open(id_path, "wb") as f:
        f.write(id.file.read())
    with open(resume_path, "wb") as f:
        f.write(resume.file.read())

    # Mark as pending for review
    with get_conn() as conn:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "verified" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN verified INTEGER DEFAULT 0")
        if "verification_status" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN verification_status TEXT DEFAULT 'none'")
        conn.execute(
            "UPDATE users SET verification_status = 'pending' WHERE email = ?",
            (user["email"],)
        )
    return {"status": "pending"}
