import fs from 'fs';
import os from 'os';
import path from 'path';
import { afterEach, describe, expect, it } from 'vitest';

const {
  REQUIRED_CHECKLIST_COUNT,
  buildReport,
  writeJsonReport,
  writeMarkdownReport
} = require('../scripts/qa-phase2-audit.js');

const tempDirs: string[] = [];

afterEach(() => {
  for (const dir of tempDirs.splice(0)) {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

function createTempProject() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'qa-phase2-audit-'));
  tempDirs.push(root);
  return root;
}

describe('qa-phase2-audit', () => {
  it('buildReport 应生成第二阶段完整清单结构', () => {
    const report = buildReport({
      projectRoot: path.resolve(__dirname, '..'),
      generatedAt: '2026-04-14T00:00:00.000Z'
    });

    expect(report.meta.generatedAt).toBe('2026-04-14T00:00:00.000Z');
    expect(report.summary.totalItems).toBe(REQUIRED_CHECKLIST_COUNT);
    expect(report.categories).toHaveLength(5);
    expect(typeof report.summary.completed).toBe('boolean');
    expect(report.summary.passedItems + report.summary.failedItems).toBe(REQUIRED_CHECKLIST_COUNT);
  });

  it('writeJsonReport 与 writeMarkdownReport 应写出报告文件', () => {
    const tempRoot = createTempProject();
    const report = buildReport({
      projectRoot: path.resolve(__dirname, '..'),
      generatedAt: '2026-04-14T00:00:00.000Z'
    });

    const jsonPath = writeJsonReport(report, path.join(tempRoot, 'reports', 'qa_phase2_audit.json'));
    const markdownPath = writeMarkdownReport(report, path.join(tempRoot, 'reports', 'qa-phase2-audit-report.md'));

    expect(fs.existsSync(jsonPath)).toBe(true);
    expect(fs.existsSync(markdownPath)).toBe(true);

    const parsed = JSON.parse(fs.readFileSync(jsonPath, 'utf8'));
    expect(parsed.summary.totalItems).toBe(REQUIRED_CHECKLIST_COUNT);

    const markdown = fs.readFileSync(markdownPath, 'utf8');
    expect(markdown).toContain('质量保证第二阶段自动化审查报告');
    expect(markdown).toContain('上线前检查清单');
  });

  it('在最小工程目录下应判定为未完成', () => {
    const tempRoot = createTempProject();
    const report = buildReport({
      projectRoot: tempRoot,
      generatedAt: '2026-04-14T00:00:00.000Z'
    });

    expect(report.summary.totalItems).toBe(REQUIRED_CHECKLIST_COUNT);
    expect(report.summary.completed).toBe(false);
    expect(report.summary.failedItems).toBeGreaterThan(0);
  });
});
