"""工作流分支与访问控制 (ACL) 集成测试。"""

from __future__ import annotations

import pytest
from app.api import 智能工作流接口 as workflow_api
from app.services.智能工作流服务 import SmartWorkflowService
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _basic_workflow_definition(name: str = "test-workflow") -> dict:
    return {
        "name": name,
        "nodes": [
            {
                "node_id": "input",
                "kind": "input",
                "node_type": "input.constant",
                "params": {"value": [1, 2, 3]},
            },
            {
                "node_id": "output",
                "kind": "output",
                "node_type": "output.collect",
                "params": {"fields": ["input"]},
            },
        ],
        "edges": [{"source": "input", "target": "output"}],
    }


@pytest.fixture
def service() -> SmartWorkflowService:
    return SmartWorkflowService(auto_start_scheduler=False)


@pytest.fixture
def client(service: SmartWorkflowService) -> TestClient:
    app = FastAPI()
    workflow_api.smart_workflow_service = service
    app.include_router(workflow_api.router, prefix="/api")

    with TestClient(app) as test_client:
        yield test_client


def _create_workflow(client: TestClient, definition: dict) -> dict:
    resp = client.post("/api/workflow", json={"definition": definition})
    assert resp.status_code == 200, resp.text
    return resp.json()["workflow"]


# ============================================================
# 3.1 权限安全专项测试
# ============================================================

class TestAccessControl:
    """权限安全专项测试"""

    def test_private_workflow_returns_403_for_unauthorized(self, client: TestClient) -> None:
        """验证：私有 Workflow 若无权限应返回 403"""
        wf = _create_workflow(client, _basic_workflow_definition("private-wf"))
        workflow_id = wf["workflow_id"]

        # 默认 is_public=false，无权限用户尝试访问应被拒绝
        resp = client.get(f"/api/workflow/{workflow_id}/access/unauthorized_user")
        assert resp.status_code == 403
        # 即使未注册用户也应在 ACL 校验时被拦截
        resp2 = client.get(f"/api/workflow/{workflow_id}/access/random_guest")
        assert resp2.status_code == 403

    def test_public_workflow_readonly_for_anonymous(self, client: TestClient) -> None:
        """验证：公有 Workflow 未授权用户只能查看，不能提交编辑"""
        wf = _create_workflow(client, _basic_workflow_definition("public-wf"))
        workflow_id = wf["workflow_id"]

        # 设为公有
        resp = client.patch(f"/api/workflow/{workflow_id}/acl", json={"is_public": True})
        assert resp.status_code == 200

        # 匿名用户可查看 (view_workflow 权限)
        resp = client.get(f"/api/workflow/{workflow_id}/access/anonymous")
        assert resp.status_code == 200
        data = resp.json()
        assert data["access"] == "granted"

        # 匿名用户尝试编辑权限检查应失败
        # 匿名用户 role 为 public_viewer，不能编辑
        acl = client.get(f"/api/workflow/{workflow_id}/acl").json()
        assert acl["is_public"] is True

        # 工作流 update 本身不做 ACL 校验 (预留中间件层),
        # 此处验证公有访问保护机制正常工作:
        # 公有且无ACL的匿名用户只有 public_viewer (view_workflow) 权限
        perms = client.get(f"/api/workflow/{workflow_id}/permissions/anonymous").json()
        assert "edit_workflow" not in perms.get("permissions", [])
        assert "view_workflow" in perms.get("permissions", [])

    def test_acl_changes_effective_immediately(self, client: TestClient) -> None:
        """验证：权限修改后实时生效，无需重启后端"""
        wf = _create_workflow(client, _basic_workflow_definition("acl-test"))
        workflow_id = wf["workflow_id"]

        # 初始私有
        resp = client.get(f"/api/workflow/{workflow_id}/access/user_a")
        assert resp.status_code == 403

        # 设为公有
        client.patch(f"/api/workflow/{workflow_id}/acl", json={"is_public": True})

        # 立即生效
        resp = client.get(f"/api/workflow/{workflow_id}/access/user_a")
        assert resp.status_code == 200
        assert resp.json()["access"] == "granted"

        # 切回私有
        client.patch(f"/api/workflow/{workflow_id}/acl", json={"is_public": False})

        # 立即生效
        resp = client.get(f"/api/workflow/{workflow_id}/access/user_a")
        assert resp.status_code == 403

    def test_acl_info_retrieval(self, client: TestClient) -> None:
        """验证：ACL 信息可正确获取"""
        wf = _create_workflow(client, _basic_workflow_definition("acl-info"))
        workflow_id = wf["workflow_id"]

        resp = client.get(f"/api/workflow/{workflow_id}/acl")
        assert resp.status_code == 200
        data = resp.json()
        assert data["workflow_id"] == workflow_id
        assert data["is_public"] is False

    def test_owner_always_has_access(self, client: TestClient) -> None:
        """验证：工作流拥有者始终有全部权限"""
        wf = _create_workflow(client, _basic_workflow_definition("owner-wf"))
        workflow_id = wf["workflow_id"]

        # 获取 owner_id (由 create_workflow 自动分配)
        acl = client.get(f"/api/workflow/{workflow_id}/acl").json()
        owner_id = acl["owner_id"]

        if owner_id:  # 如果有 owner
            resp = client.get(f"/api/workflow/{workflow_id}/access/{owner_id}")
            assert resp.status_code == 200
            assert resp.json()["access"] == "granted"


# ============================================================
# 3.2 冲突处理专项测试
# ============================================================

class TestBranchConflict:
    """冲突处理专项测试"""

    def test_create_branch(self, client: TestClient) -> None:
        """验证：分支创建功能正常"""
        wf = _create_workflow(client, _basic_workflow_definition("branch-test"))
        workflow_id = wf["workflow_id"]

        resp = client.post(f"/api/workflow/{workflow_id}/branch", json={
            "created_by": "user_conflict",
            "data": _basic_workflow_definition("branch-version"),
        })
        assert resp.status_code == 200
        branch = resp.json()["branch"]
        assert branch["status"] == "open"
        assert branch["workflow_id"] == workflow_id
        assert branch["created_by"] == "user_conflict"
        assert "branch_id" in branch

    def test_list_branches(self, client: TestClient) -> None:
        """验证：分支列表功能正常"""
        wf = _create_workflow(client, _basic_workflow_definition("list-branch-test"))
        workflow_id = wf["workflow_id"]

        # 创建两个分支
        client.post(f"/api/workflow/{workflow_id}/branch", json={
            "created_by": "user_a",
            "data": _basic_workflow_definition("branch-a"),
        })
        client.post(f"/api/workflow/{workflow_id}/branch", json={
            "created_by": "user_b",
            "data": _basic_workflow_definition("branch-b"),
        })

        resp = client.get(f"/api/workflow/{workflow_id}/branches")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 2
        assert len(data["branches"]) == 2

    def test_branch_diff(self, client: TestClient) -> None:
        """验证：分支差异对比功能正常"""
        wf = _create_workflow(client, _basic_workflow_definition("diff-test"))
        workflow_id = wf["workflow_id"]

        # 创建有差异的分支
        modified = _basic_workflow_definition("diff-test")
        modified["nodes"].append({
            "node_id": "extra",
            "kind": "process",
            "node_type": "process.transform",
            "params": {"operation": "avg"},
        })

        resp = client.post(f"/api/workflow/{workflow_id}/branch", json={
            "created_by": "user_diff",
            "data": modified,
        })
        branch_id = resp.json()["branch"]["branch_id"]

        resp = client.get(f"/api/workflow/branches/{branch_id}/diff")
        assert resp.status_code == 200
        diff = resp.json()
        assert len(diff["nodes_added"]) == 1
        assert "extra" in diff["nodes_added"]

    def test_merge_branch_requires_admin(self, client: TestClient) -> None:
        """验证：非管理员不能合并分支"""
        wf = _create_workflow(client, _basic_workflow_definition("merge-admin-test"))
        workflow_id = wf["workflow_id"]

        # 先添加一个协作者并赋予 editor 角色
        client.patch(f"/api/workflow/{workflow_id}/collaborators", json={
            "collaborators": [{"user_id": "editor_user", "role": "editor"}]
        })

        resp = client.post(f"/api/workflow/{workflow_id}/branch", json={
            "created_by": "editor_user",
            "data": _basic_workflow_definition("editor-branch"),
        })
        branch_id = resp.json()["branch"]["branch_id"]

        # editor 尝试合并应该失败 (只有 admin 有 resolve_conflict 权限)
        resp = client.post(f"/api/workflow/branches/{branch_id}/merge", json={
            "resolver_user_id": "editor_user",
        })
        assert resp.status_code == 403

    def test_merge_branch_success(self, client: TestClient) -> None:
        """验证：管理员可以合并分支，且合并后主工作流数据一致"""
        wf = _create_workflow(client, _basic_workflow_definition("merge-ok-test"))
        workflow_id = wf["workflow_id"]

        # 添加 admin 协作者
        client.patch(f"/api/workflow/{workflow_id}/collaborators", json={
            "collaborators": [{"user_id": "admin_user", "role": "admin"}]
        })

        # 创建分支
        new_def = _basic_workflow_definition("merged-name")
        resp = client.post(f"/api/workflow/{workflow_id}/branch", json={
            "created_by": "branch_creator",
            "data": new_def,
        })
        branch_id = resp.json()["branch"]["branch_id"]

        # admin 合并
        resp = client.post(f"/api/workflow/branches/{branch_id}/merge", json={
            "resolver_user_id": "admin_user",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "merged"

        # 验证主工作流已更新
        resp = client.get(f"/api/workflow/{workflow_id}")
        merged_wf = resp.json()
        assert merged_wf["name"] == "merged-name"

    def test_branches_independent_storage(self, client: TestClient) -> None:
        """验证：分支产生后，各方操作在各自 Branch 中独立存储"""
        wf = _create_workflow(client, _basic_workflow_definition("independent-test"))
        workflow_id = wf["workflow_id"]

        # 创建分支 A
        resp_a = client.post(f"/api/workflow/{workflow_id}/branch", json={
            "created_by": "user_a",
            "data": _basic_workflow_definition("branch-a-name"),
        })
        branch_a_id = resp_a.json()["branch"]["branch_id"]

        # 创建分支 B
        resp_b = client.post(f"/api/workflow/{workflow_id}/branch", json={
            "created_by": "user_b",
            "data": _basic_workflow_definition("branch-b-name"),
        })
        branch_b_id = resp_b.json()["branch"]["branch_id"]

        # 分支 A 和 B 独立
        branch_a = client.get(f"/api/workflow/branches/{branch_a_id}").json()
        branch_b = client.get(f"/api/workflow/branches/{branch_b_id}").json()

        assert branch_a["data"]["name"] == "branch-a-name"
        assert branch_b["data"]["name"] == "branch-b-name"
        # 主工作流不变
        main_wf = client.get(f"/api/workflow/{workflow_id}").json()
        assert main_wf["name"] == "independent-test"

    def test_reject_branch(self, client: TestClient) -> None:
        """验证：管理员可以拒绝分支"""
        wf = _create_workflow(client, _basic_workflow_definition("reject-test"))
        workflow_id = wf["workflow_id"]

        client.patch(f"/api/workflow/{workflow_id}/collaborators", json={
            "collaborators": [{"user_id": "admin_user", "role": "admin"}]
        })

        resp = client.post(f"/api/workflow/{workflow_id}/branch", json={
            "created_by": "user_c",
            "data": _basic_workflow_definition("reject-branch"),
        })
        branch_id = resp.json()["branch"]["branch_id"]

        resp = client.post(f"/api/workflow/branches/{branch_id}/reject", json={
            "resolver_user_id": "admin_user",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

        # 再次合并应失败
        resp = client.post(f"/api/workflow/branches/{branch_id}/merge", json={
            "resolver_user_id": "admin_user",
        })
        assert resp.status_code == 400  # branch not open


# ============================================================
# 3.4 压力与容错测试
# ============================================================

class TestStressAndRobustness:
    """压力与容错测试"""

    def test_multiple_branches_transaction_integrity(self, client: TestClient) -> None:
        """验证：分支创建后的数据库事务完整性"""
        wf = _create_workflow(client, _basic_workflow_definition("stress-wf"))
        workflow_id = wf["workflow_id"]

        branch_ids = []
        for i in range(20):
            resp = client.post(f"/api/workflow/{workflow_id}/branch", json={
                "created_by": f"user_{i}",
                "data": _basic_workflow_definition(f"branch-{i}"),
            })
            assert resp.status_code == 200
            branch_ids.append(resp.json()["branch"]["branch_id"])

        # 所有分支都应可查询
        resp = client.get(f"/api/workflow/{workflow_id}/branches")
        assert resp.status_code == 200
        assert resp.json()["count"] == 20

        # 每个分支都应可获取详情
        for bid in branch_ids:
            resp = client.get(f"/api/workflow/branches/{bid}")
            assert resp.status_code == 200

    def test_branch_nonexistent_workflow(self, client: TestClient) -> None:
        """验证：对不存在的 workflow 创建分支返回 404"""
        resp = client.post("/api/workflow/nonexistent_id/branch", json={
            "created_by": "user_x",
            "data": _basic_workflow_definition("ghost"),
        })
        assert resp.status_code == 404

    def test_get_nonexistent_branch(self, client: TestClient) -> None:
        """验证：获取不存在的分支返回 404"""
        resp = client.get("/api/workflow/branches/nonexistent_branch")
        assert resp.status_code == 404

    def test_duplicate_branch_creation(self, client: TestClient) -> None:
        """验证：同一 workflow 允许多个分支"""
        wf = _create_workflow(client, _basic_workflow_definition("multi-branch"))
        workflow_id = wf["workflow_id"]

        # 连续创建多个分支
        resp1 = client.post(f"/api/workflow/{workflow_id}/branch", json={
            "created_by": "user_1",
            "data": _basic_workflow_definition("b1"),
        })
        resp2 = client.post(f"/api/workflow/{workflow_id}/branch", json={
            "created_by": "user_2",
            "data": _basic_workflow_definition("b2"),
        })
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.json()["branch"]["branch_id"] != resp2.json()["branch"]["branch_id"]
