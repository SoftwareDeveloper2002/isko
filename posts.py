
from fastapi import APIRouter, HTTPException, status, Header
from pydantic import BaseModel
from typing import List
from database import get_conn
from utility import get_current_user_from_auth_header
from secrets import token_urlsafe

router = APIRouter(prefix="/posts", tags=["posts"])

class Comment(BaseModel):
    id: str
    post_id: str
    author_email: str
    content: str
    created_at: str

class Post(BaseModel):
    id: str
    author_email: str
    content: str
    created_at: str
    comments: List[Comment] = []

class PostCreateRequest(BaseModel):
    content: str

class CommentCreateRequest(BaseModel):
    content: str

@router.post("", response_model=Post, status_code=status.HTTP_201_CREATED)
def create_post(payload: PostCreateRequest, authorization: str | None = Header(default=None)):
    user = get_current_user_from_auth_header(authorization)
    post_id = token_urlsafe(10)
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO posts (id, author_email, content, created_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (post_id, user["email"], payload.content.strip())
        )
        row = conn.execute(
            """
            SELECT id, author_email, content, created_at FROM posts WHERE id = ?
            """,
            (post_id,)
        ).fetchone()
        post = dict(row)
        post["comments"] = []
    return post

@router.get("", response_model=List[Post])
def list_posts():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, author_email, content, created_at FROM posts ORDER BY created_at DESC"
        ).fetchall()
        posts = []
        for row in rows:
            post = dict(row)
            comments = conn.execute(
                "SELECT id, post_id, author_email, content, created_at FROM comments WHERE post_id = ? ORDER BY created_at ASC",
                (row["id"],)
            ).fetchall()
            post["comments"] = [dict(c) for c in comments]
            posts.append(post)
    return posts

@router.post("/{post_id}/comments", response_model=Comment, status_code=status.HTTP_201_CREATED)
def add_comment(post_id: str, payload: CommentCreateRequest, authorization: str | None = Header(default=None)):
    user = get_current_user_from_auth_header(authorization)
    comment_id = token_urlsafe(10)
    with get_conn() as conn:
        post = conn.execute("SELECT id FROM posts WHERE id = ?", (post_id,)).fetchone()
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        conn.execute(
            """
            INSERT INTO comments (id, post_id, author_email, content, created_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (comment_id, post_id, user["email"], payload.content.strip())
        )
        row = conn.execute(
            "SELECT id, post_id, author_email, content, created_at FROM comments WHERE id = ?",
            (comment_id,)
        ).fetchone()
    return dict(row)


@router.delete("/{post_id}/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(post_id: str, comment_id: str, authorization: str | None = Header(default=None)):
    user = get_current_user_from_auth_header(authorization)
    with get_conn() as conn:
        row = conn.execute("SELECT author_email FROM comments WHERE id = ? AND post_id = ?", (comment_id, post_id)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Comment not found")
        if row["author_email"] != user["email"]:
            raise HTTPException(status_code=403, detail="Not authorized to delete this comment")
        conn.execute("DELETE FROM comments WHERE id = ? AND post_id = ?", (comment_id, post_id))
    return None

@router.put("/{post_id}", response_model=Post)
def update_post(post_id: str, payload: PostCreateRequest, authorization: str | None = Header(default=None)):
    user = get_current_user_from_auth_header(authorization)
    with get_conn() as conn:
        row = conn.execute("SELECT author_email FROM posts WHERE id = ?", (post_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Post not found")
        if row["author_email"] != user["email"]:
            raise HTTPException(status_code=403, detail="Not authorized to edit this post")
        conn.execute(
            "UPDATE posts SET content = ? WHERE id = ?",
            (payload.content.strip(), post_id)
        )
        updated = conn.execute(
            "SELECT id, author_email, content, created_at FROM posts WHERE id = ?",
            (post_id,)
        ).fetchone()
        post = dict(updated)
        comments = conn.execute(
            "SELECT id, post_id, author_email, content, created_at FROM comments WHERE post_id = ? ORDER BY created_at ASC",
            (post_id,)
        ).fetchall()
        post["comments"] = [dict(c) for c in comments]
    return post
