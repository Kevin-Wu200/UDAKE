#!/usr/bin/env python3
"""将 API v1 调用信息迁移为 v2。"""

from __future__ import annotations

import argparse
import json
from urllib.parse import urlsplit, urlunsplit


def upgrade_url(url: str) -> str:
    parts = urlsplit(url)
    path = parts.path
    if path == "/api/v1":
        path = "/api/v2"
    elif path.startswith("/api/v1/"):
        path = "/api/v2" + path[len("/api/v1") :]
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))


def migrate_payload(payload: dict) -> dict:
    migrated = dict(payload)
    if "url" in migrated and isinstance(migrated["url"], str):
        migrated["url"] = upgrade_url(migrated["url"])

    headers = dict(migrated.get("headers") or {})
    headers["X-API-Version"] = "2.0"
    migrated["headers"] = headers
    return migrated


def main() -> int:
    parser = argparse.ArgumentParser(description="将 API v1 调用配置迁移为 v2")
    parser.add_argument("input", help="输入 JSON 文件路径")
    parser.add_argument("-o", "--output", help="输出 JSON 文件路径，默认打印到标准输出")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    migrated = migrate_payload(data)
    rendered = json.dumps(migrated, ensure_ascii=False, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(rendered + "\n")
    else:
        print(rendered)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
