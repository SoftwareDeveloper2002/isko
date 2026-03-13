from fastapi import Response

from fastapi import APIRouter, Header, status, HTTPException
from models import UserPublic, AuthResponse, RegisterRequest, LoginRequest
from database import get_conn
from utility import get_current_user_from_auth_header, find_user_by_email, hash_password
from secrets import token_urlsafe

router = APIRouter(prefix="/auth", tags=["auth"])

# Explicit OPTIONS handlers for CORS preflight
@router.options("/login")
def options_login():
    return Response(status_code=200)

@router.options("/register")
def options_register():
    return Response(status_code=200)

@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest) -> UserPublic:
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT email FROM users WHERE email = ?",
            (payload.email.lower(),),
        ).fetchone()

        if existing is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

        conn.execute(
            """
            INSERT INTO users (email, name, password_hash, role)
            VALUES (?, ?, ?, ?)
            """,
            (
                payload.email.lower(),
                payload.name.strip(),
                hash_password(payload.password),
                payload.role,
            ),
        )

    return UserPublic(name=payload.name.strip(), email=payload.email.lower(), role=payload.role)

@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest) -> AuthResponse:
    user = find_user_by_email(payload.email)

    if user is None or user.get("password_hash") != hash_password(payload.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    token = token_urlsafe(32)

    with get_conn() as conn:
        conn.execute("INSERT INTO sessions (token, email) VALUES (?, ?)", (token, user["email"]))

    return AuthResponse(
        access_token=token,
        role=user["role"],
        name=user["name"],
        email=user["email"],
    )

@router.get("/me", response_model=UserPublic)
def me(authorization: str | None = Header(default=None)) -> UserPublic:
    # ...existing code from main.py...
    pass
