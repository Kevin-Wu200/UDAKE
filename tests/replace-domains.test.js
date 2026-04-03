import fs from 'fs';
import os from 'os';
import path from 'path';
import { fileURLToPath } from 'url';
import { afterEach, describe, expect, it } from 'vitest';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const {
  applyReplacers,
  loadEnvFile,
  resolveEnvFile,
  parseArgs,
  run
} = await import('../scripts/replace-domains.js');

const tempDirs = [];

function createTempDir() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'replace-domains-'));
  tempDirs.push(dir);
  return dir;
}

afterEach(() => {
  for (const dir of tempDirs.splice(0)) {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

describe('replace-domains 脚本', () => {
  it('应正确替换 JSON 中的文档和视频域名且不影响第三方域名', () => {
    const source = JSON.stringify(
      {
        list: [
          {
            help: {
              doc: 'https://docs.udake.local/workflow/data-import',
              video: 'https://video.udake.local/tutorials/data-import',
              thirdParty: '@geoscene/core'
            }
          }
        ]
      },
      null,
      2
    );

    const result = applyReplacers(source);

    expect(result.total).toBe(2);
    expect(result.content).toContain('${OFFICIAL_WEB}/docs/workflow/data-import');
    expect(result.content).toContain('${OFFICIAL_WEB}/videos/tutorials/data-import');
    expect(result.content).toContain('@geoscene/core');
  });

  it('应正确替换 Markdown 不同格式中的硬编码链接', () => {
    const source = [
      '- [UDAKE 社区论坛](https://community.udake.io)',
      "url: 'https://update.udake.com/releases'"
    ].join('\n');

    const result = applyReplacers(source);

    expect(result.total).toBe(2);
    expect(result.content).toContain('[UDAKE 社区论坛](${OFFICIAL_WEB}/community)');
    expect(result.content).toContain("url: '${OFFICIAL_WEB}/updates/releases'");
  });

  it('应可解析 env 文件并选择正确 mode 文件', () => {
    const envPath = resolveEnvFile('testing', '');
    const env = loadEnvFile(envPath);

    expect(env.OFFICIAL_WEB).toBeTruthy();
    expect(env.ADMIN_WEB).toBeTruthy();
  });

  it('应将替换后的文件输出到 dist 目录并保留源文件', () => {
    const tempDir = createTempDir();
    const sourceRoot = path.join(tempDir, 'workspace');
    fs.mkdirSync(sourceRoot, { recursive: true });

    const targetPath = path.join(sourceRoot, 'configs', 'workflow-wizards.json');
    fs.mkdirSync(path.dirname(targetPath), { recursive: true });
    fs.writeFileSync(
      targetPath,
      '{"help":{"doc":"https://docs.udake.local/workflow/a","video":"https://video.udake.local/tutorials/a"}}',
      'utf8'
    );

    const envPath = path.join(sourceRoot, 'test.env');
    fs.writeFileSync(envPath, 'OFFICIAL_WEB=https://x.example\nADMIN_WEB=https://admin.example\n', 'utf8');

    const outDir = path.join(sourceRoot, 'dist');
    const report = run({
      mode: 'production',
      envFile: envPath,
      outDir,
      targets: [targetPath]
    });

    const outputPath = path.join(outDir, targetPath);
    const source = fs.readFileSync(targetPath, 'utf8');
    const output = fs.readFileSync(outputPath, 'utf8');

    expect(report.results[0].total).toBe(2);
    expect(source).toContain('https://docs.udake.local/workflow/a');
    expect(output).toContain('${OFFICIAL_WEB}/docs/workflow/a');
    expect(output).toContain('${OFFICIAL_WEB}/videos/tutorials/a');
  });

  it('应支持命令行参数解析', () => {
    const options = parseArgs([
      '--mode=testing',
      '--out-dir=dist/custom',
      '--targets=configs/workflow-wizards.json,docs/系统文档.md'
    ]);

    expect(options.mode).toBe('testing');
    expect(options.outDir.endsWith(path.join('dist', 'custom'))).toBe(true);
    expect(options.targets).toHaveLength(2);
  });
});
