#!/usr/bin/env node
/* eslint-disable no-console */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const TARGET_DIR = path.join(ROOT, 'apps', 'frontend', 'js');
const FILE_EXT = new Set(['.ts', '.tsx', '.js', '.jsx']);
const TSCONFIG_PATH = path.join(ROOT, 'configs', 'tsconfig.json');
const REQUIRED_STRICT_FLAGS = [
  'strict',
  'noImplicitAny',
  'strictNullChecks',
  'strictFunctionTypes',
  'strictBindCallApply',
  'strictPropertyInitialization',
  'noImplicitThis',
  'alwaysStrict'
];

function walk(dir, out = []) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    if (entry.name.startsWith('.')) continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walk(full, out);
    } else if (FILE_EXT.has(path.extname(entry.name))) {
      out.push(full);
    }
  }
  return out;
}

function countMatches(text, pattern) {
  const matches = text.match(pattern);
  return matches ? matches.length : 0;
}

function safeReadJson(filePath) {
  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch (error) {
    console.error(`[type-completeness] 无法读取 JSON: ${filePath}`);
    throw error;
  }
}

function checkStrictFlags() {
  const tsconfig = safeReadJson(TSCONFIG_PATH);
  const compilerOptions = tsconfig.compilerOptions || {};
  const missing = REQUIRED_STRICT_FLAGS.filter((flag) => compilerOptions[flag] !== true);
  return {
    missing,
    compilerOptions
  };
}

const files = walk(TARGET_DIR);
let typedHints = 0;
let anyHints = 0;
let unknownHints = 0;
let tsIgnoreHints = 0;
const anyByFile = [];

for (const file of files) {
  const content = fs.readFileSync(file, 'utf8');
  const typedInFile =
    countMatches(content, /:\s*[A-Za-z_][A-Za-z0-9_<>,\s\[\]\|&?]*/g) +
    countMatches(content, /\bas\s+[A-Za-z_][A-Za-z0-9_<>,\s\[\]\|&?]*/g) +
    countMatches(content, /\binterface\s+[A-Za-z_]/g) +
    countMatches(content, /\btype\s+[A-Za-z_]/g);
  const anyInFile =
    countMatches(content, /:\s*any\b/g) +
    countMatches(content, /\bas\s+any\b/g) +
    countMatches(content, /Record<\s*string\s*,\s*any\s*>/g) +
    countMatches(content, /Array<\s*any\s*>/g);
  const unknownInFile = countMatches(content, /:\s*unknown\b/g) + countMatches(content, /\bas\s+unknown\b/g);
  const tsIgnoreInFile = countMatches(content, /@ts-ignore/g);

  typedHints += typedInFile;
  anyHints += anyInFile;
  unknownHints += unknownInFile;
  tsIgnoreHints += tsIgnoreInFile;

  if (anyInFile > 0) {
    anyByFile.push({
      file: path.relative(ROOT, file),
      anyHints: anyInFile,
      typedHints: typedInFile
    });
  }
}

const denominator = Math.max(1, typedHints + anyHints + tsIgnoreHints);
const completeness = ((typedHints - anyHints * 1.5 - tsIgnoreHints * 2) / denominator) * 100;
const rounded = Math.max(0, Math.min(100, Number(completeness.toFixed(2))));
const threshold = Number(process.env.TYPE_COMPLETENESS_THRESHOLD || '85');
const strictFlagCheck = checkStrictFlags();

console.log('[type-completeness]');
console.log(`files=${files.length}`);
console.log(`typed_hints=${typedHints}`);
console.log(`any_hints=${anyHints}`);
console.log(`unknown_hints=${unknownHints}`);
console.log(`ts_ignore_hints=${tsIgnoreHints}`);
console.log(`completeness=${rounded}%`);
console.log(`threshold=${threshold}%`);
console.log(`strict_flags_ok=${strictFlagCheck.missing.length === 0}`);

if (anyByFile.length > 0) {
  const topFiles = anyByFile
    .sort((a, b) => b.anyHints - a.anyHints)
    .slice(0, 10);
  console.log('top_any_files=');
  topFiles.forEach((item) => {
    console.log(`  - ${item.file}: any=${item.anyHints}, typed=${item.typedHints}`);
  });
}

if (strictFlagCheck.missing.length > 0) {
  console.error(`Missing strict flags: ${strictFlagCheck.missing.join(', ')}`);
}

if (rounded < threshold || strictFlagCheck.missing.length > 0) {
  console.error(`Type completeness ${rounded}% is below threshold ${threshold}%`);
  process.exit(1);
}
