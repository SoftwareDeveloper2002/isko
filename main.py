from __future__ import annotations
from hashlib import sha256
from pathlib import Path
import re
from secrets import token_urlsafe
import sqlite3
from models import UserPublic, AuthResponse, RegisterRequest, LoginRequest, ProjectResponse, WalletResponse, WalletWithdrawRequest
from project_utils import get_project_applications, get_project_attachments
from typing import Literal
from models import UserPublic, AuthResponse, RegisterRequest, LoginRequest,ProjectResponse, WalletResponse, WalletWithdrawRequest, ThemePreferenceResponse
from fastapi import FastAPI, File, Header, HTTPException, Response, UploadFile, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field
from developer import router as developer_router
from student import router as student_router


Role = Literal["student", "developer"]
ProjectType = Literal["web", "mobile", "both"]
ThemePreference = str




BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "iskolardev.db"
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)



from auth import router as auth_router
from projects import router as projects_router
from wallet import router as wallet_router
from preferences import router as preferences_router
from root import router as root_router
from posts import router as posts_router

app = FastAPI(title="IskolarDev API", version="1.0.0")
app.include_router(developer_router)
app.include_router(student_router)
app.include_router(posts_router)
app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(wallet_router)
app.include_router(preferences_router)
app.include_router(root_router)

app.add_middleware(
	CORSMiddleware,
	allow_origins=[
		"http://localhost:4200",
		"http://127.0.0.1:4200",
	],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

# Explicit OPTIONS handlers for CORS preflight
from fastapi.responses import Response as FastAPIResponse

@app.options("/auth/login")
def options_auth_login():
	return FastAPIResponse(status_code=200)

@app.options("/auth/register")
def options_auth_register():
	return FastAPIResponse(status_code=200)


UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

def hash_password(password: str) -> str:
	return sha256(password.encode("utf-8")).hexdigest()


def get_conn() -> sqlite3.Connection:
	conn = sqlite3.connect(DB_FILE)
	conn.row_factory = sqlite3.Row
	return conn


def init_db() -> None:
	with get_conn() as conn:
		conn.execute("""
CREATE TABLE IF NOT EXISTS posts (
	id TEXT PRIMARY KEY,
	author_email TEXT NOT NULL,
	content TEXT NOT NULL,
	created_at TEXT DEFAULT CURRENT_TIMESTAMP,
	FOREIGN KEY(author_email) REFERENCES users(email)
)
""")
		conn.execute("""
CREATE TABLE IF NOT EXISTS comments (
	id TEXT PRIMARY KEY,
	post_id TEXT NOT NULL,
	author_email TEXT NOT NULL,
	content TEXT NOT NULL,
	created_at TEXT DEFAULT CURRENT_TIMESTAMP,
	FOREIGN KEY(post_id) REFERENCES posts(id),
	FOREIGN KEY(author_email) REFERENCES users(email)
)
""")
		conn.execute("""
CREATE TABLE IF NOT EXISTS users (
	email TEXT PRIMARY KEY,
	name TEXT NOT NULL,
	password_hash TEXT NOT NULL,
	role TEXT NOT NULL CHECK (role IN ('student', 'developer'))
)
""")
		conn.execute("""
CREATE TABLE IF NOT EXISTS sessions (
	token TEXT PRIMARY KEY,
	email TEXT NOT NULL,
	created_at TEXT DEFAULT CURRENT_TIMESTAMP,
	FOREIGN KEY(email) REFERENCES users(email)
)
""")
		conn.execute("""
CREATE TABLE IF NOT EXISTS projects (
	id TEXT PRIMARY KEY,
	project_type TEXT NOT NULL CHECK (project_type IN ('web', 'mobile', 'both')),
	title TEXT NOT NULL,
	description TEXT NOT NULL,
	budget REAL NOT NULL,
	owner_email TEXT NOT NULL,
	approved_developer_email TEXT,
	created_at TEXT DEFAULT CURRENT_TIMESTAMP,
	FOREIGN KEY(owner_email) REFERENCES users(email)
)
""")
		conn.execute("""
CREATE TABLE IF NOT EXISTS project_applications (
	project_id TEXT NOT NULL,
	developer_email TEXT NOT NULL,
	status TEXT NOT NULL CHECK (status IN ('pending', 'approved')),
	created_at TEXT DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY(project_id, developer_email),
	FOREIGN KEY(project_id) REFERENCES projects(id),
	FOREIGN KEY(developer_email) REFERENCES users(email)
)
""")
		conn.execute("""
CREATE TABLE IF NOT EXISTS project_attachments (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	project_id TEXT NOT NULL,
	stored_name TEXT NOT NULL,
	original_name TEXT NOT NULL,
	mime_type TEXT,
	size_bytes INTEGER NOT NULL,
	created_at TEXT DEFAULT CURRENT_TIMESTAMP,
	FOREIGN KEY(project_id) REFERENCES projects(id)
)
""")
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS wallet_transactions (
				id TEXT PRIMARY KEY,
				developer_email TEXT NOT NULL,
				title TEXT NOT NULL,
				amount REAL NOT NULL,
				type TEXT NOT NULL CHECK (type IN ('credit', 'debit')),
				source_project_id TEXT,
				created_at TEXT DEFAULT CURRENT_TIMESTAMP,
				FOREIGN KEY(developer_email) REFERENCES users(email),
				FOREIGN KEY(source_project_id) REFERENCES projects(id)
			)
			"""
		)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS user_preferences (
				email TEXT PRIMARY KEY,
				theme TEXT NOT NULL DEFAULT 'preset:ocean',
				primary_color TEXT NOT NULL DEFAULT '#0f766e',
				secondary_color TEXT NOT NULL DEFAULT '#eef6ff',
				brand_name TEXT NOT NULL DEFAULT 'IskolarDev',
				brand_logo TEXT NOT NULL DEFAULT '/iskolarDevLogo.png',
				updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
				FOREIGN KEY(email) REFERENCES users(email)
			)
			"""
		)

		# Migrate old theme schemas to flexible preset/custom schema.
		table_sql_row = conn.execute(
			"SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'user_preferences'"
		).fetchone()
		table_sql = (table_sql_row["sql"] if table_sql_row else "") or ""
		if "'light', 'dark'" in table_sql or "'ocean', 'sunset', 'forest', 'midnight'" in table_sql:
			conn.execute(
				"""
				CREATE TABLE IF NOT EXISTS user_preferences_new (
					email TEXT PRIMARY KEY,
					theme TEXT NOT NULL DEFAULT 'preset:ocean',
					primary_color TEXT NOT NULL DEFAULT '#0f766e',
					secondary_color TEXT NOT NULL DEFAULT '#eef6ff',
					brand_name TEXT NOT NULL DEFAULT 'IskolarDev',
					brand_logo TEXT NOT NULL DEFAULT '/iskolarDevLogo.png',
					updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
					FOREIGN KEY(email) REFERENCES users(email)
				)
				"""
			)
			conn.execute(
				"""
				INSERT OR REPLACE INTO user_preferences_new (
					email,
					theme,
					primary_color,
					secondary_color,
					brand_name,
					brand_logo,
					updated_at
				)
				SELECT
					email,
					CASE
						WHEN theme IN ('dark', 'midnight') THEN 'preset:midnight'
						WHEN theme = 'sunset' THEN 'preset:sunset'
						WHEN theme = 'forest' THEN 'preset:forest'
						ELSE 'preset:ocean'
					END,
					CASE
						WHEN theme IN ('dark', 'midnight') THEN '#0ea5e9'
						WHEN theme = 'sunset' THEN '#c2410c'
						WHEN theme = 'forest' THEN '#166534'
						ELSE '#0f766e'
					END,
					CASE
						WHEN theme IN ('dark', 'midnight') THEN '#0f172a'
						WHEN theme = 'sunset' THEN '#fff4eb'
						WHEN theme = 'forest' THEN '#eefaf2'
						ELSE '#eef6ff'
					END,
					'IskolarDev',
					'/iskolarDevLogo.png',
					updated_at
				FROM user_preferences
				"""
			)
			conn.execute("DROP TABLE user_preferences")
			conn.execute("ALTER TABLE user_preferences_new RENAME TO user_preferences")

		columns = {
			row["name"]
			for row in conn.execute("PRAGMA table_info(user_preferences)").fetchall()
		}
		if "brand_name" not in columns:
			conn.execute(
				"ALTER TABLE user_preferences ADD COLUMN brand_name TEXT NOT NULL DEFAULT 'IskolarDev'"
			)
		if "brand_logo" not in columns:
			conn.execute(
				"ALTER TABLE user_preferences ADD COLUMN brand_logo TEXT NOT NULL DEFAULT '/iskolarDevLogo.png'"
			)
		if "theme_color" not in columns:
			conn.execute(
				"ALTER TABLE user_preferences ADD COLUMN theme_color TEXT NOT NULL DEFAULT '#0f766e'"
			)


def is_valid_hex_color(value: str) -> bool:
	return bool(re.fullmatch(r"#[0-9a-fA-F]{6}", value.strip()))


@app.on_event("startup")
def startup() -> None:
	init_db()


def row_to_user(row: sqlite3.Row) -> dict:
	return {
		"email": row["email"],
		"name": row["name"],
		"password_hash": row["password_hash"],
		"role": row["role"],
	}



def find_project_by_id(conn: sqlite3.Connection, project_id: str) -> dict | None:
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

	return row_to_project(conn, row)


def find_user_by_email(email: str) -> dict | None:
	target = email.strip().lower()
	with get_conn() as conn:
		row = conn.execute(
			"SELECT email, name, password_hash, role FROM users WHERE email = ?",
			(target,),
		).fetchone()

		if not row:
			return None

		return row_to_user(row)


def get_wallet_transactions(conn: sqlite3.Connection, developer_email: str) -> list[dict]:
	rows = conn.execute(
		"""
		SELECT id, title, amount, type, created_at
		FROM wallet_transactions
		WHERE developer_email = ?
		ORDER BY created_at DESC
		""",
		(developer_email,),
	).fetchall()

	return [
		{
			"id": row["id"],
			"title": row["title"],
			"amount": float(row["amount"]),
			"type": row["type"],
			"date": row["created_at"],
		}
		for row in rows
	]


def get_wallet_balance(conn: sqlite3.Connection, developer_email: str) -> float:
	row = conn.execute(
		"""
		SELECT
			COALESCE(SUM(CASE WHEN type = 'credit' THEN amount ELSE 0 END), 0) -
			COALESCE(SUM(CASE WHEN type = 'debit' THEN amount ELSE 0 END), 0) AS balance
		FROM wallet_transactions
		WHERE developer_email = ?
		""",
		(developer_email,),
	).fetchone()

	if not row:
		return 0.0

	return round(float(row["balance"]), 2)


def create_wallet_transaction(
	conn: sqlite3.Connection,
	developer_email: str,
	title: str,
	amount: float,
	transaction_type: Literal["credit", "debit"],
	source_project_id: str | None = None,
) -> None:
	conn.execute(
		"""
		INSERT INTO wallet_transactions (id, developer_email, title, amount, type, source_project_id)
		VALUES (?, ?, ?, ?, ?, ?)
		""",
		(
			token_urlsafe(12),
			developer_email,
			title,
			round(float(amount), 2),
			transaction_type,
			source_project_id,
		),
	)


def parse_bearer_token(authorization: str | None) -> str:
	if not authorization:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authorization header")

	try:
		scheme, token = authorization.split(" ", 1)
	except ValueError as exc:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization header") from exc

	if scheme.lower() != "bearer" or not token:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token")

	return token


def get_current_user_from_auth_header(authorization: str | None) -> dict:
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

		return row_to_user(row)


@app.get("/")
def root() -> dict[str, str]:
	return {"message": "IskolarDev FastAPI backend is running"}


@app.get("/health")
def health() -> dict[str, str]:
	return {"status": "ok"}


@app.post("/auth/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
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


@app.post("/auth/login", response_model=AuthResponse)
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


@app.get("/auth/me", response_model=UserPublic)
def me(authorization: str | None = Header(default=None)) -> UserPublic:
	user = get_current_user_from_auth_header(authorization)

	return UserPublic(name=user["name"], email=user["email"], role=user["role"])


@app.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreateRequest, authorization: str | None = Header(default=None)) -> ProjectResponse:
	user = get_current_user_from_auth_header(authorization)

	if user.get("role") != "student":
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only students can post projects")

	project_id = token_urlsafe(10)

	project = {
		"id": project_id,
		"project_type": payload.project_type,
		"title": payload.title.strip(),
		"description": payload.description.strip(),
		"budget": round(float(payload.budget), 2),
		"owner_email": user["email"],
		"approved_developer_email": None,
		"applications": [],
	}


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

	return ProjectResponse(**project)

@app.post("/developer/verify")
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

	# Mark as pending for review (pseudo: add verified and verification_status columns if not exist)
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


@app.get("/projects", response_model=list[ProjectResponse])
def list_projects(authorization: str | None = Header(default=None)) -> list[ProjectResponse]:
	user = get_current_user_from_auth_header(authorization)

	with get_conn() as conn:
		if user.get("role") == "student":
			rows = conn.execute(
				"""
				SELECT id, project_type, title, description, budget, owner_email, approved_developer_email
				FROM projects
				WHERE owner_email = ?
				ORDER BY created_at DESC
				""",
				(user["email"],),
			).fetchall()
		else:
			rows = conn.execute(
				"""
				SELECT id, project_type, title, description, budget, owner_email, approved_developer_email
				FROM projects
				ORDER BY created_at DESC
				"""
			).fetchall()

		projects = [row_to_project(conn, row) for row in rows]

	return [ProjectResponse(**project) for project in projects]


@app.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, authorization: str | None = Header(default=None)) -> ProjectResponse:
	user = get_current_user_from_auth_header(authorization)

	with get_conn() as conn:
		project = find_project_by_id(conn, project_id)

	if project is None:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

	if user.get("role") == "student" and project.get("owner_email") != user.get("email"):
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to view this project")

	return ProjectResponse(**project)


@app.post("/projects/{project_id}/apply", response_model=ProjectResponse)
def apply_to_project(project_id: str, authorization: str | None = Header(default=None)) -> ProjectResponse:
	user = get_current_user_from_auth_header(authorization)

	if user.get("role") != "developer":
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only developers can apply")

	# Developer verification check
	with get_conn() as conn:
		dev = conn.execute(
			"SELECT verified FROM users WHERE email = ?",
			(user["email"],)
		).fetchone()
		if not dev or not dev[0]:
			raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Developer must verify account by uploading valid ID and resume before applying to projects.")

	with get_conn() as conn:
		project = find_project_by_id(conn, project_id)
		if project is None:
			raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

		if project.get("owner_email") == user.get("email"):
			raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot apply to your own project")

		if project.get("approved_developer_email"):
			raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Project already has an approved developer")

		already_applied = conn.execute(
			"""
			SELECT 1 FROM project_applications
			WHERE project_id = ? AND developer_email = ?
			""",
			(project_id, user["email"]),
		).fetchone()

		if already_applied:
			raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You already applied to this project")

		conn.execute(
			"""
			INSERT INTO project_applications (project_id, developer_email, status)
			VALUES (?, ?, 'pending')
			""",
			(project_id, user["email"]),
		)

		updated = find_project_by_id(conn, project_id)
		if updated is None:
			raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

		return ProjectResponse(**updated)


@app.post("/projects/{project_id}/approve", response_model=ProjectResponse)
def approve_project_application(
	project_id: str,
	payload: ProjectApproveRequest,
	authorization: str | None = Header(default=None),
) -> ProjectResponse:
	user = get_current_user_from_auth_header(authorization)

	if user.get("role") != "student":
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only students can approve applications")

	with get_conn() as conn:
		project = find_project_by_id(conn, project_id)
		if project is None:
			raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

		if project.get("owner_email") != user.get("email"):
			raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to approve this project")

		found = conn.execute(
			"""
			SELECT 1 FROM project_applications
			WHERE project_id = ? AND developer_email = ?
			""",
			(project_id, payload.developer_email),
		).fetchone()

		if not found:
			raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

		conn.execute(
			"UPDATE project_applications SET status = 'pending' WHERE project_id = ?",
			(project_id,),
		)
		conn.execute(
			"""
			UPDATE project_applications
			SET status = 'approved'
			WHERE project_id = ? AND developer_email = ?
			""",
			(project_id, payload.developer_email),
		)
		conn.execute(
			"UPDATE projects SET approved_developer_email = ? WHERE id = ?",
			(payload.developer_email, project_id),
		)

		already_credited = conn.execute(
			"""
			SELECT 1
			FROM wallet_transactions
			WHERE developer_email = ?
			  AND source_project_id = ?
			  AND type = 'credit'
			""",
			(payload.developer_email, project_id),
		).fetchone()

		if not already_credited:
			create_wallet_transaction(
				conn,
				developer_email=payload.developer_email,
				title=f"Project Approved: {project.get('title', 'Project')}",
				amount=float(project.get("budget", 0)),
				transaction_type="credit",
				source_project_id=project_id,
			)

		updated = find_project_by_id(conn, project_id)
		if updated is None:
			raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

		return ProjectResponse(**updated)


@app.put("/projects/{project_id}", response_model=ProjectResponse)
def update_project(
	project_id: str,
	payload: ProjectUpdateRequest,
	authorization: str | None = Header(default=None),
) -> ProjectResponse:
	user = get_current_user_from_auth_header(authorization)

	if user.get("role") != "student":
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only students can edit projects")

	with get_conn() as conn:
		project = find_project_by_id(conn, project_id)
		if project is None:
			raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

		if project.get("owner_email") != user.get("email"):
			raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to edit this project")

		conn.execute(
			"""
			UPDATE projects
			SET project_type = ?, title = ?, description = ?, budget = ?
			WHERE id = ?
			""",
			(
				payload.project_type,
				payload.title.strip(),
				payload.description.strip(),
				round(float(payload.budget), 2),
				project_id,
			),
		)

		updated = find_project_by_id(conn, project_id)
		if updated is None:
			raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

		return ProjectResponse(**updated)


@app.delete(
	"/projects/{project_id}",
	status_code=status.HTTP_204_NO_CONTENT,
	response_class=Response,
	response_model=None,
)
def delete_project(project_id: str, authorization: str | None = Header(default=None)) -> Response:
	user = get_current_user_from_auth_header(authorization)

	if user.get("role") != "student":
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only students can delete projects")

	with get_conn() as conn:
		project = find_project_by_id(conn, project_id)
		if project is None:
			raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

		if project.get("owner_email") != user.get("email"):
			raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to delete this project")

		rows = conn.execute(
			"SELECT stored_name FROM project_attachments WHERE project_id = ?",
			(project_id,),
		).fetchall()
		for row in rows:
			attachment_path = UPLOADS_DIR / row["stored_name"]
			if attachment_path.exists():
				attachment_path.unlink()

		conn.execute("DELETE FROM project_attachments WHERE project_id = ?", (project_id,))
		conn.execute("DELETE FROM project_applications WHERE project_id = ?", (project_id,))
		conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))

	return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/projects/{project_id}/attachments", response_model=ProjectResponse)
def upload_project_attachment(
	project_id: str,
	attachment: UploadFile = File(...),
	authorization: str | None = Header(default=None),
) -> ProjectResponse:
	user = get_current_user_from_auth_header(authorization)

	if user.get("role") != "student":
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only students can upload attachments")

	with get_conn() as conn:
		project = find_project_by_id(conn, project_id)
		if project is None:
			raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

		if project.get("owner_email") != user.get("email"):
			raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to upload for this project")

		if not attachment.filename:
			raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File name is required")

		suffix = Path(attachment.filename).suffix.lower()
		allowed_suffixes = {".pdf", ".doc", ".docx"}
		if suffix not in allowed_suffixes:
			raise HTTPException(
				status_code=status.HTTP_400_BAD_REQUEST,
				detail="Only PDF, DOC, and DOCX files are allowed",
			)

		content = attachment.file.read()
		size_bytes = len(content)
		max_size = 10 * 1024 * 1024
		if size_bytes <= 0:
			raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")
		if size_bytes > max_size:
			raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large (max 10MB)")

		stored_name = f"{project_id}_{token_urlsafe(8)}{suffix}"
		destination = UPLOADS_DIR / stored_name
		destination.write_bytes(content)

		conn.execute(
			"""
			INSERT INTO project_attachments (project_id, stored_name, original_name, mime_type, size_bytes)
			VALUES (?, ?, ?, ?, ?)
			""",
			(
				project_id,
				stored_name,
				attachment.filename,
				attachment.content_type,
				size_bytes,
			),
		)

		updated = find_project_by_id(conn, project_id)
		if updated is None:
			raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

		return ProjectResponse(**updated)


@app.get("/wallet", response_model=WalletResponse)
def get_wallet(authorization: str | None = Header(default=None)) -> WalletResponse:
	user = get_current_user_from_auth_header(authorization)

	if user.get("role") != "developer":
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only developers can access wallet")

	with get_conn() as conn:
		balance = get_wallet_balance(conn, user["email"])
		transactions = get_wallet_transactions(conn, user["email"])

	return WalletResponse(
		balance=balance,
		transactions=[WalletTransactionResponse(**entry) for entry in transactions],
	)


@app.post("/wallet/withdraw", response_model=WalletResponse)
def withdraw_wallet(payload: WalletWithdrawRequest, authorization: str | None = Header(default=None)) -> WalletResponse:
	user = get_current_user_from_auth_header(authorization)

	if user.get("role") != "developer":
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only developers can withdraw")

	amount = round(float(payload.amount), 2)
	if amount <= 0:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Withdrawal amount must be greater than zero")

	with get_conn() as conn:
		balance = get_wallet_balance(conn, user["email"])
		if amount > balance:
			raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient wallet balance")

		create_wallet_transaction(
			conn,
			developer_email=user["email"],
			title="Withdrawal Request",
			amount=amount,
			transaction_type="debit",
		)

		updated_balance = get_wallet_balance(conn, user["email"])
		transactions = get_wallet_transactions(conn, user["email"])

	return WalletResponse(
		balance=updated_balance,
		transactions=[WalletTransactionResponse(**entry) for entry in transactions],
	)


@app.get("/preferences/theme", response_model=ThemePreferenceResponse)
def get_theme_preference(current_user = Depends(get_current_user_from_auth_header)):
    # Example: fetch theme from DB
    conn = get_conn()
    row = conn.execute(
        "SELECT theme_color, dark_mode FROM preferences WHERE developer_email = ?",
        (current_user.email,)
    ).fetchone()

    if not row:
        # Provide a default response if no row exists
        return ThemePreferenceResponse(
            developer_email=current_user.email,
            theme_color="#ffffff",
            dark_mode=False
        )

    return ThemePreferenceResponse(
        developer_email=current_user.email,
        theme_color=row["theme_color"],
        dark_mode=bool(row["dark_mode"])
    )

@app.put("/preferences/theme", response_model=ThemePreferenceResponse)
def update_theme_preference(
	payload: ThemePreferenceUpdateRequest,
	authorization: str | None = Header(default=None),
) -> ThemePreferenceResponse:
	user = get_current_user_from_auth_header(authorization)

	if not is_valid_hex_color(payload.primary_color) or not is_valid_hex_color(payload.secondary_color):
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid color format")

	brand_name = payload.brand_name.strip()
	brand_logo = payload.brand_logo.strip()
	if not brand_name:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Brand name is required")
	if len(brand_name) > 80:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Brand name is too long")
	if not brand_logo:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Brand logo path is required")

	with get_conn() as conn:
		conn.execute(
			"""
			INSERT INTO user_preferences (
				email,
				theme,
				primary_color,
				secondary_color,
				brand_name,
				brand_logo,
				updated_at
			)
			VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
			ON CONFLICT(email) DO UPDATE SET
				theme = excluded.theme,
				primary_color = excluded.primary_color,
				secondary_color = excluded.secondary_color,
				brand_name = excluded.brand_name,
				brand_logo = excluded.brand_logo,
				updated_at = CURRENT_TIMESTAMP
			""",
			(
				user["email"],
				payload.theme,
				payload.primary_color,
				payload.secondary_color,
				brand_name,
				brand_logo,
			),
		)

	return ThemePreferenceResponse(
		theme=payload.theme,
		primary_color=payload.primary_color,
		secondary_color=payload.secondary_color,
		brand_name=brand_name,
		brand_logo=brand_logo,
	)

