#!/usr/bin/env node
/*
 * drift-check.stub.js — MINIMAL HONEST STUB. No dependencies.
 *
 * What it does (deliberately small): scans a doc for `path:line` style truth
 * citations and verifies each cited file exists and has at least that many lines.
 * It does NOT verify the cited line actually says what the doc claims — that is
 * project-specific. Implement the real drift checks for YOUR project here.
 *
 * Build this alongside your docs, not after.
 *
 * Usage: node drift-check.stub.js <doc-file>
 * Exit:  0 = all citations resolvable, 1 = drift found, 2 = bad usage.
 */
'use strict';
const fs = require('fs');

const doc = process.argv[2];
if (!doc) {
  console.error('usage: node drift-check.stub.js <doc-file>');
  process.exit(2);
}

let text;
try {
  text = fs.readFileSync(doc, 'utf8');
} catch (e) {
  console.error(`cannot read doc: ${doc} (${e.message})`);
  process.exit(2);
}

// Matches things like  src/app/foo.ts:123  — tune this regex for your project.
const CITATION = /\b([\w./-]+\.[A-Za-z0-9]+):(\d+)\b/g;

let drift = 0;
let checked = 0;
let m;
while ((m = CITATION.exec(text)) !== null) {
  const [, file, lineStr] = m;
  const line = parseInt(lineStr, 10);
  checked++;
  let ok = false;
  try {
    const lines = fs.readFileSync(file, 'utf8').split('\n').length;
    ok = line >= 1 && line <= lines;
  } catch (_) {
    ok = false;
  }
  if (!ok) {
    drift++;
    console.error(`DRIFT: ${doc} cites ${file}:${line} but it does not resolve`);
  }
}

console.log(`checked ${checked} citation(s), ${drift} drift`);
process.exit(drift > 0 ? 1 : 0);
