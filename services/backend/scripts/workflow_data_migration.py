"""工作流协作数据迁移 CLI。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.auth_db.database import create_auth_engine, create_auth_session_factory
from app.auth_db.workflow_migration import ImportOptions, WorkflowMigrationToolkit
from app.services.智能工作流服务 import SmartWorkflowService


def _build_toolkit() -> WorkflowMigrationToolkit:
    engine = create_auth_engine()
    session_factory = create_auth_session_factory(engine)
    return WorkflowMigrationToolkit(session_factory=session_factory)


def _parse_import_options(args: argparse.Namespace) -> ImportOptions:
    return ImportOptions(
        batch_size=int(args.batch_size),
        retry_times=int(args.retry_times),
        continue_on_error=bool(args.continue_on_error),
        conflict_strategy=str(args.conflict_strategy),
        partial_commit=bool(args.partial_commit),
        workers=int(args.workers),
    )


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="工作流协作数据迁移工具")
    sub = parser.add_subparsers(dest="command", required=True)

    export_cmd = sub.add_parser("export", help="从内存服务导出迁移文件")
    export_cmd.add_argument("--output-dir", required=True, help="导出目录")
    export_cmd.add_argument("--incremental-since", default="", help="增量导出起点，ISO8601")
    export_cmd.add_argument("--no-resume", action="store_true", help="禁用断点续传")
    export_cmd.add_argument("--no-compress", action="store_true", help="禁用压缩导出")

    import_cmd = sub.add_parser("import", help="导入迁移包到数据库")
    import_cmd.add_argument("--source", required=True, help="迁移包目录或 .tar.gz 文件")
    import_cmd.add_argument("--journal-path", default="", help="导入日志输出路径")
    import_cmd.add_argument("--batch-size", type=int, default=200, help="批量提交大小")
    import_cmd.add_argument("--retry-times", type=int, default=2, help="错误重试次数")
    import_cmd.add_argument(
        "--conflict-strategy",
        choices=["upsert", "skip", "error"],
        default="upsert",
        help="冲突处理策略",
    )
    import_cmd.add_argument("--continue-on-error", action="store_true", default=True, help="启用错误后继续")
    import_cmd.add_argument("--partial-commit", action="store_true", default=True, help="启用分批提交")
    import_cmd.add_argument("--workers", type=int, default=4, help="并行转换线程数")

    verify_cmd = sub.add_parser("verify", help="验证迁移结果")
    verify_cmd.add_argument("--source", required=True, help="迁移包目录或 .tar.gz 文件")
    verify_cmd.add_argument("--report-path", default="", help="输出报告路径")

    rollback_cmd = sub.add_parser("rollback", help="根据 journal 回滚导入")
    rollback_cmd.add_argument("--journal-path", required=True, help="导入日志路径")
    rollback_cmd.add_argument("--output-log", default="", help="回滚日志输出路径")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "export":
        service = SmartWorkflowService(auto_start_scheduler=False)
        toolkit = WorkflowMigrationToolkit(session_factory=None)
        result = toolkit.export_from_memory_service(
            service=service,
            output_dir=args.output_dir,
            incremental_since=args.incremental_since or None,
            resume=not args.no_resume,
            compress=not args.no_compress,
        )
        _print_json(result)
        return 0

    toolkit = _build_toolkit()
    if args.command == "import":
        options = _parse_import_options(args)
        result = toolkit.import_snapshot(
            source=args.source,
            options=options,
            journal_path=args.journal_path or None,
        )
        _print_json(result)
        return 0

    if args.command == "verify":
        result = toolkit.verify_snapshot_vs_database(args.source)
        if args.report_path:
            report_path = Path(args.report_path).expanduser().resolve()
            report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        _print_json(result)
        return 0

    if args.command == "rollback":
        result = toolkit.rollback_from_journal(
            journal_path=args.journal_path,
            output_log=args.output_log or None,
        )
        _print_json(result)
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
