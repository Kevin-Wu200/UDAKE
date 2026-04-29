#!/usr/bin/env python3
"""通过脚本直接向认证库 users 表添加用户。"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

# 允许在仓库根目录直接执行 `python scripts/init_admin.py`
PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "services" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import inspect  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402

from app.auth.security import hash_password  # noqa: E402
from app.config import settings  # noqa: E402
from app.auth_db.models import User  # noqa: E402
from app.auth_db.session import get_auth_session_factory  # noqa: E402

ALLOWED_ROLES = {"user", "admin", "enterprise", "company_admin", "super_admin"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="初始化用户到 PostgreSQL 数据库 udake_auth.users"
    )
    parser.add_argument("--username", required=True, help="用户名")
    parser.add_argument("--email", required=True, help="邮箱")
    parser.add_argument("--password", required=True, help="密码（会存储为加密哈希）")
    parser.add_argument(
        "--role",
        required=True,
        choices=sorted(ALLOWED_ROLES),
        help="用户角色",
    )
    return parser.parse_args()


def fail(message: str) -> int:
    print(f"[失败] {message}")
    return 1


def _patch_placeholder_db_url_for_local_dev() -> None:
    """
    如果配置仍是仓库默认占位账号（udake/change_me），
    则回退为当前系统用户名 + PostgreSQL Unix Socket 连接。
    """
    configured_url = str(settings.AUTH_DATABASE_URL or settings.DATABASE_URL or "").strip()
    if not configured_url:
        return

    parsed = urlparse(configured_url)
    is_placeholder_user = parsed.username == "udake"
    is_placeholder_password = parsed.password == "change_me"
    is_local_host = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    is_auth_db = (parsed.path or "").lstrip("/") == "udake_auth"

    if not (is_placeholder_user and is_placeholder_password and is_local_host and is_auth_db):
        return

    local_user = (os.getenv("USER") or getpass.getuser() or "").strip()
    if not local_user:
        return

    # Unix socket + peer auth，避免 localhost 密码认证导致的角色/密码问题。
    fallback_url = f"postgresql+psycopg2://{local_user}@/udake_auth"
    settings.AUTH_DATABASE_URL = fallback_url
    settings.DATABASE_URL = fallback_url
    print(f"[提示] 检测到占位数据库账号，已回退为本机用户连接: {local_user}@/udake_auth")


def main() -> int:
    args = parse_args()
    username = args.username.strip()
    email = args.email.strip().lower()
    role = args.role.strip()
    plain_password = args.password

    if not username:
        return fail("username 不能为空")
    if not email:
        return fail("email 不能为空")
    if not plain_password:
        return fail("password 不能为空")

    try:
        _patch_placeholder_db_url_for_local_dev()
        password_hash = hash_password(plain_password)
        session_factory = get_auth_session_factory()
    except Exception as exc:
        return fail(f"初始化数据库连接或密码哈希失败: {exc}")

    db = session_factory()
    try:
        inspector = inspect(db.bind)
        user_table_columns = {col["name"] for col in inspector.get_columns("users")}
        has_status = "status" in user_table_columns
        has_failed_login_attempts = "failed_login_attempts" in user_table_columns
        has_lock_until = "lock_until" in user_table_columns
        has_lock_reason = "lock_reason" in user_table_columns
        has_is_email_verified = "is_email_verified" in user_table_columns

        username_query_cols = [User.id, User.username, User.email]
        email_query_cols = [User.id, User.username, User.email]
        if has_status:
            username_query_cols.append(User.status)
            email_query_cols.append(User.status)

        username_conflict = db.query(*username_query_cols).filter(User.username == username).first()
        email_conflict = db.query(*email_query_cols).filter(User.email == email).first()

        username_conflict_status = getattr(username_conflict, "status", None) if username_conflict else None
        email_conflict_status = getattr(email_conflict, "status", None) if email_conflict else None

        reusable_deleted_user = None
        if (
            username_conflict
            and email_conflict
            and username_conflict.id == email_conflict.id
            and username_conflict_status == "deleted"
        ):
            reusable_deleted_user = db.query(User).filter(User.id == username_conflict.id).first()

        if reusable_deleted_user is not None:
            reusable_deleted_user.password_hash = password_hash
            reusable_deleted_user.role = role
            if has_status:
                reusable_deleted_user.status = "active"
            if has_is_email_verified:
                reusable_deleted_user.is_email_verified = True
            if has_failed_login_attempts:
                reusable_deleted_user.failed_login_attempts = 0
            if has_lock_until:
                reusable_deleted_user.lock_until = None
            if has_lock_reason:
                reusable_deleted_user.lock_reason = None
            db.commit()
            db.refresh(reusable_deleted_user)
            user = reusable_deleted_user
        else:
            conflict_messages = []
            if username_conflict:
                conflict_messages.append(
                    "username 冲突: "
                    f"id={username_conflict.id}, username={username_conflict.username}, "
                    f"email={username_conflict.email}, status={username_conflict_status}"
                )
            if email_conflict and (not username_conflict or email_conflict.id != username_conflict.id):
                conflict_messages.append(
                    "email 冲突: "
                    f"id={email_conflict.id}, username={email_conflict.username}, "
                    f"email={email_conflict.email}, status={email_conflict_status}"
                )
            if conflict_messages:
                return fail("；".join(conflict_messages))

            user_kwargs = {
                "username": username,
                "email": email,
                "password_hash": password_hash,
                "role": role,
            }
            if has_status:
                user_kwargs["status"] = "active"
            if has_is_email_verified:
                user_kwargs["is_email_verified"] = True
            if has_failed_login_attempts:
                user_kwargs["failed_login_attempts"] = 0

            user = User(**user_kwargs)
            db.add(user)
            db.commit()
            db.refresh(user)
    except IntegrityError as exc:
        db.rollback()
        return fail(f"插入失败（唯一约束或字段约束冲突）: {exc}")
    except Exception as exc:
        db.rollback()
        return fail(f"插入失败: {exc}")
    finally:
        db.close()

    print("[通过] 用户创建成功")
    print(f"- id: {user.id}")
    print(f"- username: {user.username}")
    print(f"- email: {user.email}")
    print(f"- role: {user.role}")
    print(f"- is_email_verified: {user.is_email_verified}")
    print(f"- failed_login_attempts: {user.failed_login_attempts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
