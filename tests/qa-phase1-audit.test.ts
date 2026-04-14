import fs from 'fs';
import os from 'os';
import path from 'path';
import { afterEach, describe, expect, it } from 'vitest';

const {
  buildReport,
  collectFindings,
  detectCategory,
  writeReport
} = require('../scripts/qa-phase1-audit.js');

const tempDirs: string[] = [];

afterEach(() => {
  for (const dir of tempDirs.splice(0)) {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

function createTempProject() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'qa-phase1-audit-'));
  tempDirs.push(root);
  return root;
}

function writeFile(projectRoot: string, relativePath: string, content: string) {
  const filePath = path.join(projectRoot, relativePath);
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, content, 'utf8');
  return filePath;
}

describe('qa-phase1-audit', () => {
  it('detectCategory 应正确识别类别', () => {
    expect(detectCategory('deep_learning/model.py')).toBe('core');
    expect(detectCategory('services/api/router.py')).toBe('api');
    expect(detectCategory('apps/frontend/js/main.js')).toBe('frontend');
    expect(detectCategory('tests/security.test.ts')).toBe('tests');
    expect(detectCategory('configs/vitest.config.js')).toBe('config');
    expect(detectCategory('misc/random.txt')).toBe('other');
  });

  it('collectFindings 应识别安全与质量风险模式', () => {
    const findings = collectFindings(
      "// TODO remove\nconst x = eval('1+1');\nconst apiKey = 'abcd1234abcd1234';\nconsole.log('debug');",
      'apps/frontend/js/sample.js'
    );

    const findingIds = findings.map((item: { id: string }) => item.id);
    expect(findingIds).toContain('todo_fixme');
    expect(findingIds).toContain('dangerous_eval');
    expect(findingIds).toContain('hardcoded_secret_like');
    expect(findingIds).toContain('debug_console');
  });

  it('buildReport + writeReport 应生成结构化审查报告文件', () => {
    const root = createTempProject();
    writeFile(root, 'deep_learning/core.py', '# TODO: optimize\nprint("ok")\n');
    writeFile(root, 'services/api.py', 'token = "abc123abc123abc123"\n');
    writeFile(root, 'apps/frontend/js/view.js', 'console.log("debug")\n');
    writeFile(root, 'tests/sample.test.ts', 'it("x", () => {})\n');
    writeFile(root, 'configs/app.yml', 'name: test\n');

    const report = buildReport({
      projectRoot: root,
      scanRoots: ['deep_learning', 'services', 'apps', 'tests', 'configs'],
      generatedAt: '2026-04-14T00:00:00.000Z'
    });

    expect(report.meta.generatedAt).toBe('2026-04-14T00:00:00.000Z');
    expect(report.summary.scannedFiles).toBe(5);
    expect(report.summary.categories.core.files).toBe(1);
    expect(report.summary.categories.api.files).toBe(1);
    expect(report.summary.categories.frontend.files).toBe(1);
    expect(report.summary.categories.tests.files).toBe(1);
    expect(report.summary.categories.config.files).toBe(1);
    expect(report.summary.severity.critical).toBeGreaterThan(0);

    const outputPath = path.join(root, 'reports', 'qa_phase1_audit.json');
    const writtenPath = writeReport(report, outputPath);
    expect(fs.existsSync(writtenPath)).toBe(true);

    const parsed = JSON.parse(fs.readFileSync(writtenPath, 'utf8'));
    expect(parsed.summary.scannedFiles).toBe(5);
    expect(Array.isArray(parsed.findings)).toBe(true);
    expect(parsed.findings.length).toBeGreaterThan(0);
  });
});
