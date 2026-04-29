#!/usr/bin/env python3
"""通过脚本直接向认证库 users 表添加用户。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 允许在仓库根目录直接执行 `python scripts/init_admin.py`
PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "services" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import or_  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402

from app.auth.security import hash_password  # noqa: E402
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
        password_hash = hash_password(plain_password)
        session_factory = get_auth_session_factory()
    except Exception as exc:
        return fail(f"初始化数据库连接或密码哈希失败: {exc}")

    db = session_factory()
    try:
        exists = db.query(User.id).filter(or_(User.username == username, User.email == email)).first()
        if exists:
            return fail(f"用户已存在（username={username} 或 email={email}）")

        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            role=role,
            status="active",
            is_email_verified=True,
            failed_login_attempts=0,
        )
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
