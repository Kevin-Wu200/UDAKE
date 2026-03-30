#!/usr/bin/env node
/* eslint-disable no-console */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const TARGET_DIR = path.join(ROOT, 'apps', 'frontend', 'js');
const FILE_EXT = new Set(['.ts', '.tsx', '.js', '.jsx']);

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

const files = walk(TARGET_DIR);
let typedHints = 0;
let anyHints = 0;
let unknownHints = 0;

for (const file of files) {
  const content = fs.readFileSync(file, 'utf8');
  typedHints += countMatches(content, /:\s*[A-Za-z_][A-Za-z0-9_<>,\s\[\]\|&?]*/g);
  typedHints += countMatches(content, /\bas\s+[A-Za-z_][A-Za-z0-9_<>,\s\[\]\|&?]*/g);
  anyHints += countMatches(content, /:\s*any\b/g);
  anyHints += countMatches(content, /\bas\s+any\b/g);
  anyHints += countMatches(content, /Record<\s*string\s*,\s*any\s*>/g);
  unknownHints += countMatches(content, /:\s*unknown\b/g);
}

const denominator = Math.max(1, typedHints + anyHints);
const completeness = ((typedHints - anyHints) / denominator) * 100;
const rounded = Math.max(0, Math.min(100, Number(completeness.toFixed(2))));
const threshold = Number(process.env.TYPE_COMPLETENESS_THRESHOLD || '80');

console.log('[type-completeness]');
console.log(`files=${files.length}`);
console.log(`typed_hints=${typedHints}`);
console.log(`any_hints=${anyHints}`);
console.log(`unknown_hints=${unknownHints}`);
console.log(`completeness=${rounded}%`);
console.log(`threshold=${threshold}%`);

if (rounded < threshold) {
  console.error(`Type completeness ${rounded}% is below threshold ${threshold}%`);
  process.exit(1);
}
