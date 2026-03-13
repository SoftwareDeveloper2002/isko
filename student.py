from __future__ import annotations
from fastapi import APIRouter

router = APIRouter(prefix="/student", tags=["student"])

# Example student endpoint
@router.get("/dashboard")
def student_dashboard():
    return {"message": "Student dashboard endpoint (example)"}
