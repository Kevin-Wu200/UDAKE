#!/usr/bin/env python3
"""初始化管理员账号（开发环境）。

流程：
1) 健康检查
2) 注册管理员账号（若已存在则跳过）
3) 登录校验并确认管理员角色
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, Tuple

ADMIN_ROLES = {"admin", "super_admin", "company_admin"}


def request_json(method: str, url: str, payload: Dict[str, Any] | None = None) -> Tuple[int, Dict[str, Any]]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url=url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            body = resp.read().decode("utf-8")
            return resp.getcode(), json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            body = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            body = {"raw": raw}
        return exc.code, body


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="初始化管理员账号")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="后端地址，默认 http://127.0.0.1:8000")
    parser.add_argument("--email", required=True, help="管理员邮箱")
    parser.add_argument("--password", required=True, help="管理员密码")
    parser.add_argument(
        "--product-key",
        default="UDAKE-DEFAULT-PRODUCT-KEY",
        help="产品密钥，默认 UDAKE-DEFAULT-PRODUCT-KEY",
    )
    return parser.parse_args()


def fail(message: str) -> int:
    print(f"[失败] {message}")
    return 1


def main() -> int:
    args = parse_args()
    base = args.base_url.rstrip("/")

    print("[1/3] 健康检查...")
    status, health = request_json("GET", f"{base}/health")
    if status != 200:
        return fail(f"健康检查失败: HTTP {status}, body={health}")
    if health.get("status") != "healthy":
        return fail(f"服务状态异常: {health}")
    print(f"[通过] 服务健康: {health}")

    print("[2/3] 注册管理员账号...")
    register_payload = {
        "email": args.email,
        "password": args.password,
        "product_key": args.product_key,
    }
    status, register_resp = request_json("POST", f"{base}/api/auth/register", register_payload)
    if status in {200, 201}:
        role = str(((register_resp.get("data") or {}).get("role") or "")).strip() or "unknown"
        print(f"[通过] 注册成功，角色: {role}")
    elif status == 400 and "已注册" in json.dumps(register_resp, ensure_ascii=False):
        print("[提示] 账号已存在，跳过注册")
    else:
        return fail(f"注册失败: HTTP {status}, body={register_resp}")

    print("[3/3] 登录并校验角色...")
    login_payload = {
        "email": args.email,
        "password": args.password,
        "device_info": {},
    }
    status, login_resp = request_json("POST", f"{base}/api/auth/login", login_payload)
    if status != 200:
        return fail(f"登录失败: HTTP {status}, body={login_resp}")

    data = login_resp.get("data") or {}
    user_info = data.get("user_info") or {}
    role = str(user_info.get("role") or "").strip()
    token = str(data.get("access_token") or "")
    if not token:
        return fail("登录响应缺少 access_token")
    if role not in ADMIN_ROLES:
        return fail(f"当前账号角色不是管理员: role={role}")

    print("[通过] 管理员账号可用")
    print(f"- user_id: {user_info.get('user_id')}")
    print(f"- email: {user_info.get('email')}")
    print(f"- role: {role}")
    print(f"- access_token(前20位): {token[:20]}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
