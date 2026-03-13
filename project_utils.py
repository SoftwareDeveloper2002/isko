import sqlite3

def get_project_applications(conn: sqlite3.Connection, project_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT developer_email, status
        FROM project_applications
        WHERE project_id = ?
        ORDER BY created_at DESC
        """,
        (project_id,),
    ).fetchall()
    return [
        {
            "developer_email": row["developer_email"],
            "status": row["status"],
        }
        for row in rows
    ]

def get_project_attachments(conn: sqlite3.Connection, project_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, stored_name, original_name, mime_type, size_bytes
        FROM project_attachments
        WHERE project_id = ?
        ORDER BY created_at DESC
        """,
        (project_id,),
    ).fetchall()
    return [
        {
            "id": int(row["id"]),
            "file_name": row["original_name"],
            "file_url": f"http://127.0.0.1:8000/uploads/{row['stored_name']}",
            "mime_type": row["mime_type"],
            "size_bytes": int(row["size_bytes"]),
        }
        for row in rows
    ]
