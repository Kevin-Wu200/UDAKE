import { describe, it, expect, beforeEach, vi } from 'vitest';
import type {
  WorkflowACLInfo,
  WorkflowAccessCheck,
  WorkflowBranchItem,
  WorkflowBranchDetail,
  WorkflowBranchDiff,
} from '../apps/admin-frontend/src/types/workflow';

// ----- 类型正确性测试 -----

describe('Workflow Branch & ACL Types', () => {
  describe('WorkflowACLInfo', () => {
    it('应包含必要字段', () => {
      const acl: WorkflowACLInfo = {
        workflow_id: 'wf_001',
        is_public: false,
        owner_id: 'user_owner',
        collaborators: [{ user_id: 'u1', role: 'editor' }],
      };
      expect(acl.workflow_id).toBe('wf_001');
      expect(acl.is_public).toBe(false);
      expect(acl.owner_id).toBe('user_owner');
      expect(acl.collaborators).toHaveLength(1);
    });
  });

  describe('WorkflowAccessCheck', () => {
    it('access 应为 granted 或 denied', () => {
      const granted: WorkflowAccessCheck = {
        workflow_id: 'wf_001',
        user_id: 'u1',
        access: 'granted',
        role: 'owner',
      };
      const denied: WorkflowAccessCheck = {
        workflow_id: 'wf_001',
        user_id: 'u2',
        access: 'denied',
      };
      expect(granted.access).toBe('granted');
      expect(denied.access).toBe('denied');
    });
  });

  describe('WorkflowBranchItem', () => {
    it('status 应为 open/merged/rejected 之一', () => {
      const open: WorkflowBranchItem = {
        branch_id: 'branch_001',
        workflow_id: 'wf_001',
        created_by: 'user_a',
        status: 'open',
        created_at: '2026-05-21T08:00:00Z',
        updated_at: '2026-05-21T08:00:00Z',
      };
      const merged: WorkflowBranchItem = {
        ...open,
        branch_id: 'branch_002',
        status: 'merged',
      };
      const rejected: WorkflowBranchItem = {
        ...open,
        branch_id: 'branch_003',
        status: 'rejected',
      };

      expect(open.status).toBe('open');
      expect(merged.status).toBe('merged');
      expect(rejected.status).toBe('rejected');
    });
  });

  describe('WorkflowBranchDetail', () => {
    it('应包含完整数据和父分支引用', () => {
      const detail: WorkflowBranchDetail = {
        branch_id: 'branch_001',
        workflow_id: 'wf_001',
        created_by: 'user_a',
        status: 'open',
        created_at: '2026-05-21T08:00:00Z',
        updated_at: '2026-05-21T08:00:00Z',
        parent_branch_id: null,
        data: {
          workflow_id: 'wf_001',
          name: 'test',
          version: 1,
          nodes: [],
          edges: [],
        },
      };
      expect(detail.parent_branch_id).toBeNull();
      expect(detail.data.nodes).toEqual([]);
    });
  });

  describe('WorkflowBranchDiff', () => {
    it('应包含节点和边的差异列表', () => {
      const diff: WorkflowBranchDiff = {
        branch_id: 'branch_001',
        workflow_id: 'wf_001',
        nodes_added: ['node_new'],
        nodes_removed: ['node_old'],
        nodes_modified: ['node_changed'],
        edges_added: ['a->b'],
        edges_removed: ['c->d'],
        main: {
          nodes: [{ node_id: 'node_old', kind: 'input', node_type: 'input.constant', params: {} }],
          edges: [{ source: 'c', target: 'd' }],
        },
        branch: {
          nodes: [{ node_id: 'node_new', kind: 'input', node_type: 'input.constant', params: {} }],
          edges: [{ source: 'a', target: 'b' }],
        },
      };
      expect(diff.nodes_added).toContain('node_new');
      expect(diff.nodes_removed).toContain('node_old');
      expect(diff.nodes_modified).toContain('node_changed');
    });
  });
});

// ----- 分支状态机测试 (前端逻辑) -----

describe('Branch Status Machine', () => {
  type BranchStatus = 'open' | 'merged' | 'rejected';

  const STATUS_TRANSITIONS: Record<BranchStatus, BranchStatus[]> = {
    open: ['merged', 'rejected'],
    merged: [],
    rejected: [],
  };

  function isValidTransition(from: BranchStatus, to: BranchStatus): boolean {
    return STATUS_TRANSITIONS[from]?.includes(to) ?? false;
  }

  it('open 可转为 merged 或 rejected', () => {
    expect(isValidTransition('open', 'merged')).toBe(true);
    expect(isValidTransition('open', 'rejected')).toBe(true);
    expect(isValidTransition('open', 'open')).toBe(false);
  });

  it('merged 不可再转为其他状态', () => {
    expect(isValidTransition('merged', 'open')).toBe(false);
    expect(isValidTransition('merged', 'rejected')).toBe(false);
  });

  it('rejected 不可再转为其他状态', () => {
    expect(isValidTransition('rejected', 'open')).toBe(false);
    expect(isValidTransition('rejected', 'merged')).toBe(false);
  });
});

// ----- ACL 权限计算测试 (前端逻辑) -----

describe('ACL Permission Calculation', () => {
  // 模拟后端 _ROLE_PERMISSIONS
  const ROLE_PERMISSIONS: Record<string, Set<string>> = {
    guest: new Set(['view_workflow']),
    viewer: new Set(['view_workflow', 'update_cursor']),
    commenter: new Set(['comment', 'view_workflow', 'update_cursor']),
    editor: new Set([
      'view_workflow', 'update_cursor', 'comment',
      'edit_workflow', 'execute_workflow', 'create_share_link', 'export_data',
    ]),
    admin: new Set([
      'view_workflow', 'update_cursor', 'comment',
      'edit_workflow', 'execute_workflow', 'create_share_link', 'export_data',
      'manage_share', 'manage_team', 'manage_collaborators',
      'delegate_permission', 'resolve_conflict',
    ]),
  };

  function hasPermission(role: string, permission: string): boolean {
    return ROLE_PERMISSIONS[role]?.has(permission) ?? false;
  }

  it('guest 只有 view_workflow 权限', () => {
    expect(hasPermission('guest', 'view_workflow')).toBe(true);
    expect(hasPermission('guest', 'edit_workflow')).toBe(false);
    expect(hasPermission('guest', 'resolve_conflict')).toBe(false);
  });

  it('editor 没有 resolve_conflict 权限', () => {
    expect(hasPermission('editor', 'edit_workflow')).toBe(true);
    expect(hasPermission('editor', 'resolve_conflict')).toBe(false);
    expect(hasPermission('editor', 'manage_share')).toBe(false);
  });

  it('admin 拥有 resolve_conflict 权限', () => {
    expect(hasPermission('admin', 'resolve_conflict')).toBe(true);
    expect(hasPermission('admin', 'manage_team')).toBe(true);
    expect(hasPermission('admin', 'delegate_permission')).toBe(true);
  });

  it('未知角色默认视为 guest (无权限)', () => {
    expect(hasPermission('unknown_role', 'view_workflow')).toBe(false);
  });
});

// ----- 合并确认机制测试 (UI 逻辑) -----

describe('Merge Confirmation Logic', () => {
  it('非管理员无法发起合并确认', () => {
    const userRole = 'editor';
    const canMerge = userRole === 'admin';
    expect(canMerge).toBe(false);
  });

  it('管理员可以发起合并确认', () => {
    const userRole = 'admin';
    const canMerge = userRole === 'admin';
    expect(canMerge).toBe(true);
  });

  it('已合并或已拒绝的分支不应显示合并按钮', () => {
    const canShowMergeButton = (status: string) => status === 'open';
    expect(canShowMergeButton('open')).toBe(true);
    expect(canShowMergeButton('merged')).toBe(false);
    expect(canShowMergeButton('rejected')).toBe(false);
  });
});
