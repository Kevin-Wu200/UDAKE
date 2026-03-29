"""智能工作流服务：编排定义、执行、模板与调度。"""

from __future__ import annotations

import threading
import time
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Mapping, Optional
from uuid import uuid4

from ..workflow.engine import WorkflowEngine
from ..workflow.schema import WorkflowValidationError, get_workflow_schema
from ..workflow.templates import built_in_templates


class SmartWorkflowService:
    """智能工作流应用服务。"""

    def __init__(self, auto_start_scheduler: bool = True) -> None:
        self._lock = threading.RLock()
        self._engine = WorkflowEngine()

        self._workflows: Dict[str, Dict[str, Any]] = {}
        self._runs: Dict[str, Dict[str, Any]] = {}
        self._templates: Dict[str, Dict[str, Any]] = {
            item["template_id"]: item for item in built_in_templates()
        }
        self._schedules: Dict[str, Dict[str, Any]] = {}

        self._metrics: Dict[str, Any] = {
            "total_runs": 0,
            "success_runs": 0,
            "failed_runs": 0,
            "avg_duration_ms": 0.0,
            "last_updated_at": datetime.now(timezone.utc).isoformat(),
        }

        self._running = False
        self._scheduler_thread: Optional[threading.Thread] = None
        if auto_start_scheduler:
            self.start_scheduler()

    # -------- 生命周期 --------
    def start_scheduler(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            self._scheduler_thread = threading.Thread(
                target=self._scheduler_loop,
                name="smart-workflow-scheduler",
                daemon=True,
            )
            self._scheduler_thread.start()

    def stop_scheduler(self) -> None:
        with self._lock:
            self._running = False
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=2.0)

    # -------- 运行健康与元数据 --------
    def health_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "status": "healthy",
                "module": "smart_workflow",
                "workflow_count": len(self._workflows),
                "template_count": len(self._templates),
                "run_count": len(self._runs),
                "schedule_count": len(self._schedules),
                "scheduler_running": self._running,
            }

    def get_schema(self) -> Dict[str, Any]:
        return get_workflow_schema()

    def list_node_types(self) -> Dict[str, Any]:
        return self._engine.list_node_types()

    # -------- 工作流定义与版本 --------
    def validate_definition(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        normalized = self._engine.validate_definition(payload)
        return {
            "valid": True,
            "workflow": normalized,
            "dag_levels": normalized.get("dag_levels", []),
            "node_count": len(normalized.get("nodes", [])),
            "edge_count": len(normalized.get("edges", [])),
        }

    def create_workflow(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        normalized = self._engine.validate_definition(payload)
        workflow_id = normalized["workflow_id"]

        with self._lock:
            if workflow_id in self._workflows:
                raise ValueError(f"工作流已存在: {workflow_id}")

            now = datetime.now(timezone.utc).isoformat()
            record = {
                "workflow_id": workflow_id,
                "name": normalized["name"],
                "description": normalized.get("description", ""),
                "created_at": now,
                "updated_at": now,
                "current": normalized,
                "versions": [
                    {
                        "version": normalized["version"],
                        "created_at": now,
                        "note": "initial",
                        "definition": deepcopy(normalized),
                    }
                ],
                "collaborators": [],
            }
            self._workflows[workflow_id] = record
            return deepcopy(record)

    def list_workflows(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {
                    "workflow_id": item["workflow_id"],
                    "name": item["name"],
                    "description": item["description"],
                    "created_at": item["created_at"],
                    "updated_at": item["updated_at"],
                    "version": item["current"]["version"],
                    "collaborator_count": len(item.get("collaborators") or []),
                }
                for item in self._workflows.values()
            ]

    def get_workflow(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            item = self._workflows.get(workflow_id)
            if not item:
                return None
            return deepcopy(item)

    def update_workflow(self, workflow_id: str, updates: Mapping[str, Any], note: str = "update") -> Dict[str, Any]:
        with self._lock:
            current = self._workflows.get(workflow_id)
            if not current:
                raise KeyError(f"workflow '{workflow_id}' not found")
            merged = deepcopy(current["current"])
            for key, value in updates.items():
                if key == "workflow_id":
                    continue
                merged[key] = deepcopy(value)

            merged["workflow_id"] = workflow_id
            merged["version"] = int(current["current"]["version"]) + 1
            normalized = self._engine.validate_definition(merged)

            now = datetime.now(timezone.utc).isoformat()
            current["name"] = normalized["name"]
            current["description"] = normalized.get("description", "")
            current["updated_at"] = now
            current["current"] = normalized
            current["versions"].append(
                {
                    "version": normalized["version"],
                    "created_at": now,
                    "note": note,
                    "definition": deepcopy(normalized),
                }
            )
            return deepcopy(current)

    def delete_workflow(self, workflow_id: str) -> None:
        with self._lock:
            if workflow_id not in self._workflows:
                raise KeyError(f"workflow '{workflow_id}' not found")
            del self._workflows[workflow_id]

            # 清理相关调度
            schedule_ids = [sid for sid, schedule in self._schedules.items() if schedule["workflow_id"] == workflow_id]
            for sid in schedule_ids:
                del self._schedules[sid]

    def list_versions(self, workflow_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            current = self._workflows.get(workflow_id)
            if not current:
                raise KeyError(f"workflow '{workflow_id}' not found")
            return [
                {
                    "version": item["version"],
                    "created_at": item["created_at"],
                    "note": item["note"],
                }
                for item in current["versions"]
            ]

    def rollback_workflow(self, workflow_id: str, target_version: int) -> Dict[str, Any]:
        with self._lock:
            current = self._workflows.get(workflow_id)
            if not current:
                raise KeyError(f"workflow '{workflow_id}' not found")

            matched = next((item for item in current["versions"] if int(item["version"]) == int(target_version)), None)
            if not matched:
                raise KeyError(f"version '{target_version}' not found")

            restored = deepcopy(matched["definition"])
            restored["version"] = int(current["current"]["version"]) + 1
            restored = self._engine.validate_definition(restored)

            now = datetime.now(timezone.utc).isoformat()
            current["current"] = restored
            current["updated_at"] = now
            current["versions"].append(
                {
                    "version": restored["version"],
                    "created_at": now,
                    "note": f"rollback_to_{target_version}",
                    "definition": deepcopy(restored),
                }
            )
            return deepcopy(current)

    def export_workflow(self, workflow_id: str) -> Dict[str, Any]:
        with self._lock:
            current = self._workflows.get(workflow_id)
            if not current:
                raise KeyError(f"workflow '{workflow_id}' not found")
            return deepcopy(current["current"])

    def import_workflow(self, definition: Mapping[str, Any], overwrite: bool = False) -> Dict[str, Any]:
        normalized = self._engine.validate_definition(definition)
        workflow_id = normalized["workflow_id"]

        with self._lock:
            if workflow_id in self._workflows:
                if not overwrite:
                    raise ValueError(f"workflow '{workflow_id}' 已存在，若要覆盖请设置 overwrite=true")
                # 走 update 流程，保留版本轨迹
                return self.update_workflow(workflow_id, normalized, note="import_overwrite")

        return self.create_workflow(normalized)

    def set_collaborators(self, workflow_id: str, collaborators: List[Dict[str, Any]]) -> Dict[str, Any]:
        with self._lock:
            current = self._workflows.get(workflow_id)
            if not current:
                raise KeyError(f"workflow '{workflow_id}' not found")
            current["collaborators"] = deepcopy(collaborators)
            current["updated_at"] = datetime.now(timezone.utc).isoformat()
            return deepcopy(current)

    # -------- 执行与监控 --------
    def execute_workflow(
        self,
        workflow_id: str,
        input_variables: Optional[Mapping[str, Any]] = None,
        async_mode: bool = False,
        trigger: str = "manual",
        debug: bool = False,
    ) -> Dict[str, Any]:
        with self._lock:
            current = self._workflows.get(workflow_id)
            if not current:
                raise KeyError(f"workflow '{workflow_id}' not found")
            definition = deepcopy(current["current"])

        if not async_mode:
            result = self._engine.execute(
                definition=definition,
                input_variables=input_variables,
                trigger=trigger,
                debug=debug,
            )
            with self._lock:
                self._runs[result["run_id"]] = deepcopy(result)
            self._update_metrics(result)
            return result

        run_id = f"run_{uuid4().hex[:12]}"
        placeholder = {
            "run_id": run_id,
            "workflow_id": workflow_id,
            "workflow_version": definition["version"],
            "trigger": trigger,
            "status": "queued",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "ended_at": None,
            "duration_ms": None,
            "progress": 0.0,
            "error": None,
            "logs": [],
            "node_statuses": {},
            "node_attempts": {},
            "node_outputs": {},
            "node_timings_ms": {},
            "variables": deepcopy(definition.get("variables") or {}),
            "dag_levels": deepcopy(definition.get("dag_levels") or []),
            "summary": {
                "completed_nodes": 0,
                "failed_nodes": 0,
                "skipped_nodes": 0,
            },
        }

        with self._lock:
            self._runs[run_id] = placeholder

        thread = threading.Thread(
            target=self._execute_async,
            kwargs={
                "run_id": run_id,
                "definition": definition,
                "input_variables": deepcopy(dict(input_variables or {})),
                "trigger": trigger,
                "debug": debug,
            },
            daemon=True,
            name=f"workflow-runner-{run_id}",
        )
        thread.start()

        return deepcopy(placeholder)

    def _execute_async(
        self,
        run_id: str,
        definition: Mapping[str, Any],
        input_variables: Mapping[str, Any],
        trigger: str,
        debug: bool,
    ) -> None:
        try:
            result = self._engine.execute(
                definition=definition,
                input_variables=input_variables,
                trigger=trigger,
                debug=debug,
            )
            result["run_id"] = run_id
        except Exception as exc:  # pylint: disable=broad-except
            now = datetime.now(timezone.utc).isoformat()
            result = {
                "run_id": run_id,
                "workflow_id": definition.get("workflow_id"),
                "workflow_version": definition.get("version"),
                "trigger": trigger,
                "status": "failed",
                "started_at": now,
                "ended_at": now,
                "duration_ms": 0.0,
                "progress": 100.0,
                "error": str(exc),
                "logs": [
                    {
                        "ts": now,
                        "node_id": "__engine__",
                        "event": "engine_failed",
                        "message": str(exc),
                    }
                ],
                "node_statuses": {},
                "node_attempts": {},
                "node_outputs": {},
                "node_timings_ms": {},
                "variables": deepcopy(definition.get("variables") or {}),
                "dag_levels": deepcopy(definition.get("dag_levels") or []),
                "summary": {
                    "completed_nodes": 0,
                    "failed_nodes": 1,
                    "skipped_nodes": 0,
                },
            }

        with self._lock:
            self._runs[run_id] = deepcopy(result)
        self._update_metrics(result)

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            run = self._runs.get(run_id)
            return deepcopy(run) if run else None

    def list_runs(self, workflow_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            runs = list(self._runs.values())

        if workflow_id:
            runs = [item for item in runs if item.get("workflow_id") == workflow_id]

        runs.sort(key=lambda item: item.get("started_at", ""), reverse=True)
        trimmed = runs[: max(1, min(limit, 500))]
        return [
            {
                "run_id": item.get("run_id"),
                "workflow_id": item.get("workflow_id"),
                "workflow_version": item.get("workflow_version"),
                "status": item.get("status"),
                "trigger": item.get("trigger"),
                "started_at": item.get("started_at"),
                "ended_at": item.get("ended_at"),
                "duration_ms": item.get("duration_ms"),
                "progress": item.get("progress"),
            }
            for item in trimmed
        ]

    def get_run_logs(self, run_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            run = self._runs.get(run_id)
            if not run:
                raise KeyError(f"run '{run_id}' not found")
            return deepcopy(run.get("logs") or [])

    def get_performance_metrics(self) -> Dict[str, Any]:
        with self._lock:
            return deepcopy(self._metrics)

    def _update_metrics(self, run: Mapping[str, Any]) -> None:
        with self._lock:
            self._metrics["total_runs"] += 1
            if run.get("status") == "completed":
                self._metrics["success_runs"] += 1
            else:
                self._metrics["failed_runs"] += 1

            duration = float(run.get("duration_ms") or 0.0)
            total = self._metrics["total_runs"]
            prev_avg = float(self._metrics.get("avg_duration_ms", 0.0))
            self._metrics["avg_duration_ms"] = round(((prev_avg * (total - 1)) + duration) / total, 3)
            self._metrics["last_updated_at"] = datetime.now(timezone.utc).isoformat()

    # -------- 模板库 / 市场 --------
    def list_templates(
        self,
        category: Optional[str] = None,
        shared_only: bool = False,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            items = list(self._templates.values())

        if category:
            items = [item for item in items if str(item.get("category")) == category]
        if shared_only:
            items = [item for item in items if bool(item.get("shared", False))]

        items.sort(key=lambda item: (item.get("rating_average", 0.0), item.get("usage_count", 0)), reverse=True)
        return [deepcopy(item) for item in items[: max(1, min(limit, 500))]]

    def create_template(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        workflow = payload.get("workflow")
        if not isinstance(workflow, Mapping):
            raise ValueError("workflow 字段必填")
        normalized = self._engine.validate_definition(workflow)

        template_id = str(payload.get("template_id") or f"tpl_custom_{uuid4().hex[:10]}")
        now = datetime.now(timezone.utc).isoformat()
        template = {
            "template_id": template_id,
            "name": str(payload.get("name") or normalized["name"]),
            "category": str(payload.get("category") or "custom"),
            "tags": list(payload.get("tags") or []),
            "description": str(payload.get("description") or normalized.get("description") or ""),
            "workflow": normalized,
            "shared": bool(payload.get("shared", False)),
            "rating_average": 0.0,
            "rating_count": 0,
            "usage_count": 0,
            "ratings": [],
            "created_at": now,
            "updated_at": now,
        }

        with self._lock:
            if template_id in self._templates:
                raise ValueError(f"template '{template_id}' 已存在")
            self._templates[template_id] = template

        return deepcopy(template)

    def share_template(self, template_id: str, shared: bool = True) -> Dict[str, Any]:
        with self._lock:
            template = self._templates.get(template_id)
            if not template:
                raise KeyError(f"template '{template_id}' not found")
            template["shared"] = bool(shared)
            template["updated_at"] = datetime.now(timezone.utc).isoformat()
            return deepcopy(template)

    def rate_template(
        self,
        template_id: str,
        rating: float,
        user_id: str = "anonymous",
        comment: str = "",
    ) -> Dict[str, Any]:
        if rating < 1 or rating > 5:
            raise ValueError("rating 必须在 [1, 5]")

        with self._lock:
            template = self._templates.get(template_id)
            if not template:
                raise KeyError(f"template '{template_id}' not found")

            ratings = template.setdefault("ratings", [])
            ratings.append(
                {
                    "user_id": user_id,
                    "rating": float(rating),
                    "comment": comment,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            score_sum = sum(float(item["rating"]) for item in ratings)
            template["rating_count"] = len(ratings)
            template["rating_average"] = round(score_sum / len(ratings), 3)
            template["updated_at"] = datetime.now(timezone.utc).isoformat()
            return deepcopy(template)

    def recommend_templates(
        self,
        tags: Optional[List[str]] = None,
        category: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        tags_set = {tag.strip().lower() for tag in (tags or []) if tag and tag.strip()}
        candidates = self.list_templates(category=category, shared_only=True, limit=500)

        scored: List[Dict[str, Any]] = []
        for item in candidates:
            item_tags = {str(tag).lower() for tag in item.get("tags", [])}
            tag_score = len(tags_set.intersection(item_tags)) if tags_set else 0
            quality_score = float(item.get("rating_average", 0.0))
            usage_score = min(2.0, float(item.get("usage_count", 0)) / 10.0)
            score = tag_score * 2 + quality_score + usage_score
            scored.append({"score": round(score, 3), "template": item})

        scored.sort(key=lambda x: x["score"], reverse=True)
        return [
            {
                "score": item["score"],
                "template": item["template"],
            }
            for item in scored[: max(1, min(limit, 50))]
        ]

    def create_workflow_from_template(
        self,
        template_id: str,
        workflow_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self._lock:
            template = self._templates.get(template_id)
            if not template:
                raise KeyError(f"template '{template_id}' not found")
            workflow = deepcopy(template["workflow"])
            template["usage_count"] = int(template.get("usage_count", 0)) + 1
            template["updated_at"] = datetime.now(timezone.utc).isoformat()

        workflow["workflow_id"] = f"wf_{uuid4().hex[:12]}"
        workflow["name"] = workflow_name or f"{workflow.get('name', '模板工作流')}_实例"
        workflow["version"] = 1
        return self.create_workflow(workflow)

    def get_marketplace(self, limit: int = 20) -> List[Dict[str, Any]]:
        templates = self.list_templates(shared_only=True, limit=500)
        templates.sort(
            key=lambda item: (
                float(item.get("rating_average", 0.0)),
                int(item.get("rating_count", 0)),
                int(item.get("usage_count", 0)),
            ),
            reverse=True,
        )
        return templates[: max(1, min(limit, 100))]

    # -------- 调度 --------
    def create_schedule(
        self,
        workflow_id: str,
        interval_seconds: int,
        trigger_payload: Optional[Mapping[str, Any]] = None,
        enabled: bool = True,
    ) -> Dict[str, Any]:
        if interval_seconds < 1:
            raise ValueError("interval_seconds 必须 >= 1")

        with self._lock:
            if workflow_id not in self._workflows:
                raise KeyError(f"workflow '{workflow_id}' not found")

            schedule_id = f"sch_{uuid4().hex[:12]}"
            now = datetime.now(timezone.utc)
            schedule = {
                "schedule_id": schedule_id,
                "workflow_id": workflow_id,
                "interval_seconds": int(interval_seconds),
                "enabled": bool(enabled),
                "trigger_payload": deepcopy(dict(trigger_payload or {})),
                "next_run_at": (now + timedelta(seconds=interval_seconds)).isoformat(),
                "last_run_at": None,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }
            self._schedules[schedule_id] = schedule
            return deepcopy(schedule)

    def list_schedules(self, workflow_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            schedules = list(self._schedules.values())

        if workflow_id:
            schedules = [item for item in schedules if item["workflow_id"] == workflow_id]
        schedules.sort(key=lambda item: item["created_at"], reverse=True)
        return [deepcopy(item) for item in schedules]

    def delete_schedule(self, schedule_id: str) -> None:
        with self._lock:
            if schedule_id not in self._schedules:
                raise KeyError(f"schedule '{schedule_id}' not found")
            del self._schedules[schedule_id]

    def trigger_schedule(self, schedule_id: str) -> Dict[str, Any]:
        with self._lock:
            schedule = self._schedules.get(schedule_id)
            if not schedule:
                raise KeyError(f"schedule '{schedule_id}' not found")

            schedule["last_run_at"] = datetime.now(timezone.utc).isoformat()
            schedule["next_run_at"] = (
                datetime.now(timezone.utc) + timedelta(seconds=int(schedule["interval_seconds"]))
            ).isoformat()
            schedule["updated_at"] = datetime.now(timezone.utc).isoformat()

            workflow_id = schedule["workflow_id"]
            payload = deepcopy(schedule.get("trigger_payload") or {})

        run = self.execute_workflow(
            workflow_id=workflow_id,
            input_variables=payload,
            async_mode=True,
            trigger=f"schedule:{schedule_id}",
            debug=False,
        )
        return run

    def _scheduler_loop(self) -> None:
        while True:
            with self._lock:
                if not self._running:
                    return
                schedules = [deepcopy(item) for item in self._schedules.values() if item.get("enabled", False)]

            now = datetime.now(timezone.utc)
            for schedule in schedules:
                next_run_raw = schedule.get("next_run_at")
                if not next_run_raw:
                    continue
                try:
                    next_run_at = datetime.fromisoformat(next_run_raw)
                except Exception:  # pylint: disable=broad-except
                    continue

                if next_run_at <= now:
                    try:
                        self.trigger_schedule(schedule["schedule_id"])
                    except Exception:  # pylint: disable=broad-except
                        # 调度循环容错：失败记录在 run/error 中，不让线程退出
                        pass

            time.sleep(1.0)


# 单例
_smart_workflow_service: Optional[SmartWorkflowService] = None


def get_smart_workflow_service() -> SmartWorkflowService:
    global _smart_workflow_service
    if _smart_workflow_service is None:
        _smart_workflow_service = SmartWorkflowService()
    return _smart_workflow_service


def reset_smart_workflow_service() -> None:
    global _smart_workflow_service
    if _smart_workflow_service is not None:
        _smart_workflow_service.stop_scheduler()
    _smart_workflow_service = None


smart_workflow_service = get_smart_workflow_service()

__all__ = [
    "SmartWorkflowService",
    "smart_workflow_service",
    "get_smart_workflow_service",
    "reset_smart_workflow_service",
    "WorkflowValidationError",
]
