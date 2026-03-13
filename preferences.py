from fastapi import APIRouter, Header, status, HTTPException
from models import ThemePreferenceResponse, ThemePreferenceUpdateRequest
from database import get_conn
from utility import is_valid_hex_color, get_current_user_from_auth_header


router = APIRouter(prefix="/preferences", tags=["preferences"])


@router.get("/theme", response_model=ThemePreferenceResponse)
def get_theme_preference(authorization: str | None = Header(default=None)) -> ThemePreferenceResponse:
    user = get_current_user_from_auth_header(authorization)
    conn = get_conn()
    row = conn.execute(
        "SELECT theme, primary_color, secondary_color, brand_name, brand_logo FROM user_preferences WHERE email = ?",
        (user["email"],)
    ).fetchone()

    if not row:
        return ThemePreferenceResponse(
            theme="default",
            primary_color="#ffffff",
            theme_color="#ffffff",
            secondary_color="#000000",
            brand_name="",
            brand_logo=""
        )

    return ThemePreferenceResponse(
        theme=row["theme"],
        primary_color=row["primary_color"],
        theme_color=row["theme_color"] if "theme_color" in row.keys() else row["primary_color"],
        secondary_color=row["secondary_color"],
        brand_name=row["brand_name"],
        brand_logo=row["brand_logo"]
    )

@router.put("/theme", response_model=ThemePreferenceResponse)
def update_theme_preference(payload: ThemePreferenceUpdateRequest, authorization: str | None = Header(default=None)) -> ThemePreferenceResponse:
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
                theme_color,
                secondary_color,
                brand_name,
                brand_logo,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(email) DO UPDATE SET
                theme = excluded.theme,
                primary_color = excluded.primary_color,
                theme_color = excluded.theme_color,
                secondary_color = excluded.secondary_color,
                brand_name = excluded.brand_name,
                brand_logo = excluded.brand_logo,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                user["email"],
                payload.theme,
                payload.primary_color,
                payload.primary_color,  # theme_color (using primary_color as default)
                payload.secondary_color,
                brand_name,
                brand_logo,
            ),
        )

    return ThemePreferenceResponse(
        theme=payload.theme,
        primary_color=payload.primary_color,
        theme_color=payload.primary_color,  # theme_color (using primary_color as default)
        secondary_color=payload.secondary_color,
        brand_name=brand_name,
        brand_logo=brand_logo,
    )
