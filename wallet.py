from fastapi import APIRouter, Depends, HTTPException
from secrets import token_urlsafe
from typing import Literal
import sqlite3

from models import WalletResponse, WalletWithdrawRequest
from database import get_conn
from utility import get_current_user_from_auth_header

router = APIRouter(prefix="/wallet", tags=["wallet"])


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


# ✅ API endpoint to get wallet info
@router.get("/", response_model=WalletResponse)
def wallet_dashboard(
    user=Depends(get_current_user_from_auth_header),
    conn: sqlite3.Connection = Depends(get_conn),
):
    balance = get_wallet_balance(conn, user["email"])
    transactions = get_wallet_transactions(conn, user["email"])

    return {
        "balance": balance,
        "transactions": transactions,
    }


# ✅ API endpoint to request withdrawal
@router.post("/withdraw")
def withdraw_wallet(
    request: WalletWithdrawRequest,
    user=Depends(get_current_user_from_auth_header),
    conn: sqlite3.Connection = Depends(get_conn),
):
    balance = get_wallet_balance(conn, user["email"])

    if request.amount > balance:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    create_wallet_transaction(
        conn,
        user["email"],
        "Withdrawal request",
        request.amount,
        "debit",
    )

    conn.commit()

    return {"message": "Withdrawal request created"}
