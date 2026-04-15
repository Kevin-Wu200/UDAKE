#!/usr/bin/env node

const fs = require("fs");
const path = require("path");

const projectRoot = path.resolve(__dirname, "..");
const releaseDir = path.join(projectRoot, "release");
const targetFile = path.join(projectRoot, "UDAKE.exe");

function getLatestExeFile() {
  if (!fs.existsSync(releaseDir)) {
    throw new Error(`未找到构建产物目录: ${releaseDir}`);
  }

  const entries = fs
    .readdirSync(releaseDir, { withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name.toLowerCase().endsWith(".exe"))
    .map((entry) => {
      const fullPath = path.join(releaseDir, entry.name);
      return {
        name: entry.name,
        path: fullPath,
        mtimeMs: fs.statSync(fullPath).mtimeMs,
      };
    });

  if (entries.length === 0) {
    throw new Error(`在 ${releaseDir} 中未找到 .exe 文件`);
  }

  entries.sort((a, b) => b.mtimeMs - a.mtimeMs);
  return entries[0];
}

function copyArtifact() {
  const latest = getLatestExeFile();
  fs.copyFileSync(latest.path, targetFile);

  const sizeInMB = (fs.statSync(targetFile).size / (1024 * 1024)).toFixed(2);
  console.log("Windows 打包产物复制完成");
  console.log(`来源文件: ${latest.path}`);
  console.log(`目标文件: ${targetFile}`);
  console.log(`文件大小: ${sizeInMB} MB`);
}

try {
  copyArtifact();
} catch (error) {
  console.error(`[copy-windows-artifact] ${error.message}`);
  process.exit(1);
}
