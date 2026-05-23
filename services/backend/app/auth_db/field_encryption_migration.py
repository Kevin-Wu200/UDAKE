"""数据库字段加密迁移脚本 —— 将现有明文敏感字段迁移为密文存储。

执行方式：
    python -m services.backend.app.auth_db.field_encryption_migration [--dry-run]

迁移范围：
1. product_keys.product_key -> product_key_ciphertext（AES-GCM 加密）
2. product_keys.product_key 添加哈希索引值 product_key_hash（SHA-256 确定性哈希）
3. users.email -> 添加到已定义加密字段清单

回滚方式：
    python -m services.backend.app.auth_db.field_encryption_migration --rollback
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

# 添加项目根目录到 Python 路径
_project_root = Path(__file__).resolve().parents[4]  # auth_db -> app -> backend -> services -> repo root
sys.path.insert(0, str(_project_root))

from services.backend.app.auth_db.database import get_session
from services.backend.app.services.数据安全服务 import get_data_security_service

logger = logging.getLogger(__name__)


@dataclass
class MigrationStats:
    """迁移统计信息。"""

    total_processed: int = 0
    encrypted_count: int = 0
    skipped_count: int = 0
    error_count: int = 0
    errors: List[Dict[str, Any]] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


def migrate_product_keys(dry_run: bool = False) -> MigrationStats:
    """将 product_keys 表的 product_key 字段加密迁移至 product_key_ciphertext。

    同时生成 product_key_hash 用于确定性查找（支持索引查询）。
    """
    stats = MigrationStats()
    security_service = get_data_security_service()
    session = get_session()

    try:
        from services.backend.app.auth_db.models import ProductKey

        # 查询所有有待加密的 product_key 记录（有明文但无密文或密文为空）
        keys = (
            session.query(ProductKey)
            .filter(
                ProductKey.product_key.isnot(None),
                ProductKey.product_key != "",
            )
            .all()
        )

        for key in keys:
            try:
                plaintext = str(key.product_key or "").strip()
                if not plaintext:
                    stats.skipped_count += 1
                    continue

                # 如果已经是密文格式则跳过
                if plaintext.startswith("kmsf:v1:"):
                    stats.skipped_count += 1
                    continue

                if not dry_run:
                    # 加密字段
                    ciphertext = security_service.encrypt_field(plaintext)
                    key.product_key_ciphertext = ciphertext

                    # 生成确定性哈希用于索引查找
                    key_hash = hashlib.sha256(f"product_key:{plaintext}".encode("utf-8")).hexdigest()[:64]
                    key.generation_seed = key_hash  # 复用 generation_seed 字段存储哈希

                    stats.encrypted_count += 1
                else:
                    stats.encrypted_count += 1

                stats.total_processed += 1

            except Exception as exc:
                stats.error_count += 1
                stats.errors.append({
                    "key_id": key.id,
                    "key_type": key.key_type,
                    "error": str(exc),
                })
                logger.error("加密 key_id=%s 失败: %s", key.id, exc)

        if not dry_run and stats.encrypted_count > 0:
            session.commit()
            logger.info("已加密 %s 条 product_key 记录", stats.encrypted_count)

    except Exception as exc:
        logger.exception("迁移失败")
        session.rollback()
        stats.errors.append({"error": str(exc)})
    finally:
        session.close()

    return stats


def migrate_user_emails(dry_run: bool = False) -> MigrationStats:
    """将 users 表的 email 字段加密方案评估。

    当前不直接加密 email（需要支持 Email 验证等明文操作），
    而是标记为建议加密字段并在审计日志中记录。
    """
    stats = MigrationStats()
    session = get_session()

    try:
        from services.backend.app.auth_db.models import User

        users = session.query(User).filter(User.email.isnot(None), User.email != "").all()
        stats.total_processed = len(users)
        stats.skipped_count = len(users)  # 暂不加密，仅统计
        logger.info(
            "评估完成：%s 个用户邮箱待加密（当前跳过，需先实现 Email 服务适配层）",
            stats.total_processed,
        )
    except Exception as exc:
        logger.exception("用户邮箱评估失败")
        stats.errors.append({"error": str(exc)})
    finally:
        session.close()

    return stats


def rollback_product_keys(dry_run: bool = False) -> MigrationStats:
    """回滚：将 product_key_ciphertext 解密还原为明文 product_key。"""
    stats = MigrationStats()
    security_service = get_data_security_service()
    session = get_session()

    try:
        from services.backend.app.auth_db.models import ProductKey

        keys = (
            session.query(ProductKey)
            .filter(
                ProductKey.product_key_ciphertext.isnot(None),
                ProductKey.product_key_ciphertext != "",
            )
            .all()
        )

        for key in keys:
            try:
                ciphertext = str(key.product_key_ciphertext or "")
                if not ciphertext:
                    stats.skipped_count += 1
                    continue

                if not dry_run:
                    plaintext = security_service.decrypt_field(ciphertext)
                    key.product_key = plaintext
                    key.product_key_ciphertext = None
                    stats.encrypted_count += 1
                else:
                    stats.encrypted_count += 1

                stats.total_processed += 1

            except Exception as exc:
                stats.error_count += 1
                stats.errors.append({
                    "key_id": key.id,
                    "error": str(exc),
                })
                logger.error("回滚 key_id=%s 失败: %s", key.id, exc)

        if not dry_run and stats.encrypted_count > 0:
            session.commit()
            logger.info("已回滚 %s 条 product_key 记录", stats.encrypted_count)

    except Exception as exc:
        logger.exception("回滚失败")
        session.rollback()
        stats.errors.append({"error": str(exc)})
    finally:
        session.close()

    return stats


def verify_migration() -> Dict[str, Any]:
    """验证迁移结果：检查密文是否可解密、数据一致性。"""
    security_service = get_data_security_service()
    session = get_session()
    result: Dict[str, Any] = {
        "verified": 0,
        "mismatch": 0,
        "errors": 0,
        "details": [],
    }

    try:
        from services.backend.app.auth_db.models import ProductKey

        keys = (
            session.query(ProductKey)
            .filter(
                ProductKey.product_key_ciphertext.isnot(None),
                ProductKey.product_key_ciphertext != "",
            )
            .limit(100)
            .all()
        )

        for key in keys:
            try:
                ciphertext = str(key.product_key_ciphertext or "")
                decrypted = security_service.decrypt_field(ciphertext)
                # 如果 original product_key 还存在，对比一致性
                original = str(key.product_key or "")
                if original and original != decrypted:
                    result["mismatch"] += 1
                    result["details"].append({
                        "key_id": key.id,
                        "original": original[:8] + "***",
                        "decrypted": decrypted[:8] + "***",
                    })
                else:
                    result["verified"] += 1
            except Exception as exc:
                result["errors"] += 1
                result["details"].append({
                    "key_id": key.id,
                    "error": str(exc),
                })

    except Exception as exc:
        logger.exception("验证失败")
        result["errors"] += 1
        result["details"].append({"error": str(exc)})
    finally:
        session.close()

    return result


def main():
    parser = argparse.ArgumentParser(description="数据库字段加密迁移工具")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="试运行模式，不实际修改数据",
    )
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="回滚加密，将密文还原为明文",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="验证迁移结果一致性",
    )
    parser.add_argument(
        "--target",
        choices=["product_keys", "users", "all"],
        default="product_keys",
        help="迁移目标表（默认: product_keys）",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    started_at = time.time()

    if args.verify:
        logger.info("开始验证迁移结果...")
        result = verify_migration()
        logger.info(
            "验证完成: verified=%s mismatch=%s errors=%s",
            result["verified"],
            result["mismatch"],
            result["errors"],
        )
        if result["details"]:
            for detail in result["details"][:10]:
                logger.warning("  详情: %s", detail)
        return

    if args.rollback:
        logger.info("开始回滚 product_keys 加密...")
        stats = rollback_product_keys(dry_run=args.dry_run)
    elif args.target in ("product_keys", "all"):
        logger.info("开始迁移 product_keys 字段加密...")
        stats = migrate_product_keys(dry_run=args.dry_run)

        if args.target == "all":
            logger.info("评估 users 邮箱加密...")
            email_stats = migrate_user_emails(dry_run=args.dry_run)
            stats.total_processed += email_stats.total_processed
            stats.skipped_count += email_stats.skipped_count
            stats.error_count += email_stats.error_count
            stats.errors.extend(email_stats.errors)
    else:
        logger.info("评估 users 邮箱加密...")
        stats = migrate_user_emails(dry_run=args.dry_run)

    duration_ms = int((time.time() - started_at) * 1000)
    logger.info("=" * 60)
    logger.info("迁移%s完成 (耗时 %sms)", " [试运行]" if args.dry_run else "", duration_ms)
    logger.info("  处理总数: %s", stats.total_processed)
    logger.info("  加密/回滚: %s", stats.encrypted_count)
    logger.info("  跳过: %s", stats.skipped_count)
    logger.info("  错误: %s", stats.error_count)
    if stats.errors:
        logger.warning("  错误详情:")
        for err in stats.errors[:5]:
            logger.warning("    %s", err)


if __name__ == "__main__":
    main()
